import json  # noqa: D100
import logging
import re
from configparser import ConfigParser
from random import randint

import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from tinydb import Query, TinyDB

from database.database import PostgreClient
from models.dalle import OpenaiClient
from models.embeddings import Embeddings
from models.kandinsky import KandinskyClient
from queue_bot import add_request_to_queue, get_queue_length, start_thread

gods = [1038099964, 1030055969]
prices = {20: 80, 50: 200, 100: 390, 500: 1950, 1000: 3800, 5000: 18500}

# Configure logging settings
logging.basicConfig(filename="logs.log", format="%(asctime)s %(message)s", filemode="w")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize the ConfigParser
parser = ConfigParser()
parser.read("configs.ini")

# Get values from the config file
testing = True

token = parser["DEFAULTS"].get("TOKEN")
test_token = parser["DEFAULTS"].get("TEST_TOKEN")
yookassa_token = parser["DEFAULTS"].get("YOOKASSA_TOKEN")

delay = int(parser["DEFAULTS"].get("delay")) if not testing else 10

test_bot_name = parser["DEFAULTS"].get("test_bot_name")
bot_name = parser["DEFAULTS"].get("bot_name") if not testing else test_bot_name

kandinsky_api_key = parser["IMAGEGEN"].get("kandisky_api_key")
kandinsky_secret_key = parser["IMAGEGEN"].get("kandinsky_secret_key")
dalle_api_key = parser["IMAGEGEN"].get("dalle_api_key")

host = parser["DATABASE"].get("host")
username = parser["DATABASE"].get("username")
password = parser["DATABASE"].get("password")

user_db_name = parser["DATABASE"].get("user_db_name")
games_db_name = parser["DATABASE"].get("games_db_name")

# Initialize the telebot and OpenaiClient
bot = telebot.TeleBot(test_token if testing else token)
dalle_client = OpenaiClient(dalle_api_key)
kandinsky_client = KandinskyClient(
    "https://api-key.fusionbrain.ai/",
    kandinsky_api_key,
    kandinsky_secret_key,
)
embedding_client = Embeddings()

# Dictionary to store game data
games_db = TinyDB("database/games.json")
User = Query()
if not testing:
    database_client = PostgreClient(
        host=host,
        logger=logger,
        password=password,
        dbname=user_db_name,
        user=username,
    )
    database_client.init_user_table()

for game in games_db.all():
    game_id = game["id"]
    bot.send_message(
        int(game_id),
        "✨ *Спасибо за ожидание*. Вы можете продолжать играть.",
        parse_mode="Markdown",
    )

print("bot started")  # noqa: T201


@bot.callback_query_handler(func=lambda _: True)
def handle_query(call: telebot.types.CallbackQuery) -> None:
    """Handle button's callback.

    Parameters
    ----------
    call : telebot.types.CallbackQuery
        the call

    Returns
    -------
    None

    """
    match call.data.split(";")[0]:
        # case "model_change":
        #     selected_model = (
        #         "kandinsky" if call.data.split(";")[1] == "dall-e" else "dall-e"
        #     )
        #     bot.edit_message_text(
        #         f"Чтобы загадать слово, нажми на кнопку ниже! 😁\nМодель: *{selected_model}*\nЦена игры: *{'1 токен' if selected_model == 'kandinsky' else '4 токена'}*",
        #         call.message.chat.id,
        #         call.message.message_id,
        #         parse_mode="Markdown",
        #     )
        #     bot.edit_message_reply_markup(
        #         call.message.chat.id,
        #         call.message.message_id,
        #         reply_markup=InlineKeyboardMarkup(
        #             [
        #                 [
        #                     InlineKeyboardButton(
        #                         text="🧠 Загадать!",
        #                         url=f"https://t.me/{bot_name}?start=pick{call.message.chat.id}_{selected_model}",
        #                     ),
        #                 ],
        #                 [
        #                     InlineKeyboardButton(
        #                         text="🔁 Сменить модель",
        #                         callback_data=f"model_change;{selected_model}",
        #                     ),
        #                 ],
        #             ],
        #         ),
        #     )
        #     bot.answer_callback_query(call.id)
        case "play":
            bot.answer_callback_query(call.id)
            play(call.message)
        case "about_models":
            bot.answer_callback_query(call.id)
            models(call.message)
        case "add_balance":
            bot.edit_message_text(
                "👑 Чтобы купить токены, нажми на какую-то из кнопок ниже.\n\n😁 При покупке большого количества токенов за раз присутствует скидка!",  # noqa: E501",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
            )

            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="💳 20 токенов - 80 р.",  # noqa: RUF001,
                                callback_data="buy_tokens;20",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="💳 50 токенов - 200 р.",  # noqa: RUF001,
                                callback_data="buy_tokens;50",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="💳 100 токенов - 390 р. (-2.5%)",  # noqa: RUF001,
                                callback_data="buy_tokens;100",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="💳 500 токенов - 1950 р. (-2.5%)",  # noqa: RUF001,
                                callback_data="buy_tokens;500",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="💳 1000 токенов - 3800 р. (-5%)",  # noqa: RUF001,
                                callback_data="buy_tokens;1000",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="💳 5000 токенов - 18500 р. (-7.5%)",  # noqa: RUF001,
                                callback_data="buy_tokens;5000",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="⬅️ Назад",
                                callback_data="back_to_balance",
                            ),
                        ],
                    ],
                ),
            )

            bot.answer_callback_query(call.id)
        case "back_to_balance":
            tokens = database_client.get_user_string_by_id(str(call.from_user.id))[3]

            bot.edit_message_text(
                f"💰 Ваш баланс: *{tokens}* {get_str_token(tokens)}.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
            )

            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="➕ Пополнить баланс",  # noqa: RUF001
                                callback_data="add_balance",
                            ),
                        ],
                    ],
                ),
            )

            bot.answer_callback_query(call.id)
        case "buy_tokens":
            amount = int(call.data.split(";")[1])

            pr_data = json.dumps(
                {
                    "receipt": {
                        "items": [
                            {
                                "description": f"{amount} токенов",
                                "quantity": "1.00",
                                "amount": {
                                    "value": f"{prices[amount]}.00",
                                    "currency": "RUB",
                                },
                                "vat_code": 1,
                            },
                        ],
                    },
                },
            )

            bot.send_invoice(
                call.message.chat.id,
                f"{amount} токенов",
                "Пожалуйста, оплатите покупку по кнопке ниже. Оплата возможна только по карте. На указанный email-адрес придёт чек о покупке.",  # noqa: E501, RUF001
                f"{amount};{call.from_user.id}",
                yookassa_token,
                "RUB",
                [telebot.types.LabeledPrice(f"{amount} токенов", prices[amount] * 100)],
                need_email=True,
                send_email_to_provider=True,
                provider_data=pr_data,
            )

            logger.info(f"User {call.from_user.id} created payment for {amount} tokens")  # noqa: G004

            bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.pre_checkout_query_handler(func=lambda _: True)
def process_pre_checkout_query(
    pre_checkout_query: telebot.types.PreCheckoutQuery,
) -> None:
    """Process pre-checkout query.

    Parameters
    ----------
    pre_checkout_query : telebot.types.PreCheckoutQuery
        pre-checkout query

    Returns
    -------
    None

    """
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def handle_successful_payment(message: telebot.types.Message) -> None:
    """Handle successful payment.

    Parameters
    ----------
    message : telebot.types.Message
        successful payment message

    Returns
    -------
    None

    """
    transaction_id = message.successful_payment.provider_payment_charge_id

    tokens_got = message.successful_payment.invoice_payload.split(";")[0]
    user_id = message.successful_payment.invoice_payload.split(";")[1]

    database_client.add_credits_to_user(user_id, tokens_got)

    current_tokens = database_client.get_user_string_by_id(user_id)[3]

    bot.send_message(
        message.chat.id,
        f"👑 *Спасибо за покупку!*\n\n💸 На ваш баланс было начислено *{tokens_got} токенов*\n\n💰 Сейчас у вас *{current_tokens} {get_str_token(current_tokens)}*",  # noqa: RUF001, E501*",*",
        parse_mode="Markdown",
    )

    logger.info(
        f"User {user_id} successfully paid and got {tokens_got} tokens | tr_id {transaction_id}",  # noqa: G004, E501
    )


def contains_only_english_letters(word: str) -> bool:
    """Check if word only contains english letters.

    Parameters
    ----------
    word : str
        word that will be checked

    Returns
    -------
    bool

    """
    return bool(re.match("^[a-zA-Z]+$", word))


def get_parameter(text: str) -> str:
    """Get the argument from the command.

    Parameters
    ----------
    text : str
        the text from which to get the argument from

    Returns
    -------
    str
        the argument

    """
    try:
        return text.split()[1] if 3 > len(text.split()) > 1 else ""  # noqa: PLR2004
    except Exception:  # noqa: BLE001
        return ""


def get_price(model: str) -> int:
    """Get the price of the game.

    Parameters
    ----------
    model : str
        model name

    Returns
    -------
    int
        the price

    """
    return 1 if model == "kandinsky" else 4


@bot.message_handler(commands=["start", "help"])
def start(message: telebot.types.Message) -> None:  # noqa: PLR0912
    """Do most of the game's functions.

    Parameters
    ----------
    message : telebot.types.Message
        message

    Returns
    -------
    None

    """
    try:
        # Get the parameter from the message text
        param = get_parameter(message.text)

        # Check if the parameter is empty
        if not param:
            if message.chat.type == "private" and not testing:
                database_client.add_user_if_not_exists(message.from_user.id)

            bot.send_message(
                message.chat.id,
                "👋 *Привет!*\n\nЯ - бот, с помощью которого можно загадывать слова, чтобы твои друзья отгадывали их по сгенерированной нейросетью картинке. Я буду давать им подсказки и указывать, насколько они близки к правильному ответу.\nВ игру пока что можно играть только на английском языке.\n\n📄 Полная документация доступна [по ссылке](https://foxfil.xyz/contexto/docs).",  # noqa: E501, RUF001",",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="🎮 Играть!",
                                callback_data="play",
                            ),
                        ],
                        # [
                        #     InlineKeyboardButton(
                        #         text="📌 О моделях",
                        #         callback_data="about_models",
                        #     ),
                        # ],
                    ],
                ),
            )
        else:  # noqa: PLR5501
            # Check if the message is sent in a private chat
            if message.chat.type == "private":
                if not testing:
                    database_client.add_user_if_not_exists(message.from_user.id)

                if param.startswith("pick"):
                    # Extract the group ID from the parameter
                    group_id = param.split("_")[0][4:]
                    selected_model = param.split("_")[1]

                    if group_id.startswith("-"):
                        # Check if a game is already in progress for the group ID
                        if games_db.search(User.id == str(group_id)):
                            bot.send_message(
                                message.chat.id,
                                "❌ Игра уже идет или вы уже в очереди!",
                            )
                        elif database_client.get_user_string_by_id(
                            message.from_user.id,
                        )[3] < get_price(selected_model):
                            bot.send_message(
                                message.chat.id,
                                "❌ У вас не хватает токенов! Проверьте свой баланс используя /balance.",  # noqa: E501, RUF001
                            )
                        else:
                            # Prompt the user to send a word to be guessed
                            answer_message = bot.send_message(
                                message.chat.id,
                                f"Отправь мне слово, которое хочешь загадать! 😨\nВыбранная модель: *{selected_model}*",  # noqa: E501,, RUF001,
                                parse_mode="Markdown",
                            )
                            # Register a handler for the next message to start word picking  # noqa: E501
                            bot.register_next_step_handler(
                                answer_message,
                                start_word_picking,
                                int(group_id),
                                selected_model,
                            )
                    else:
                        bot.send_message(
                            message.chat.id,
                            "❌ Не пытайся запустить игру в личных сообщениях!",  # noqa: RUF001
                        )
            else:
                # Send an error message if the command with parameter is used in a group chat  # noqa: E501
                bot.send_message(
                    message.chat.id,
                    "❌ Команду с параметром можно использовать только в личных сообщениях!",  # noqa: E501, RUF001
                )
    except Exception as e:  # noqa: BLE001
        # Send an error message if an exception occurs
        bot.send_message(
            message.chat.id,
            f"⛔ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: RUF001, E501
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004


@bot.message_handler(commands=["play"])
def play(message: telebot.types.Message, change_model: bool = False) -> None:  # noqa: FBT002, FBT001
    """Generate the game link, send it to the chat.

    Parameters
    ----------
    message : telebot.types.Message
        model name
    change_model: bool, optional
        if the model should be changed from basic "kandinsky" to "dall-e" (default is False)

    Returns
    -------
    int
        the price

    """  # noqa: E501
    try:
        if message.chat.type != "private":
            if not games_db.search(User.id == str(message.chat.id)):
                selected_model = "kandinsky" if not change_model else "dall-e"

                bot.send_message(
                    message.chat.id,
                    f"Чтобы загадать слово, нажми на кнопку ниже! 😁\nМодель: *{selected_model}*\nЦена игры: *{'1 токен' if selected_model == 'kandinsky' else '4 токена'}*",  # noqa: RUF001,, E501,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text="🧠 Загадать!",
                                    url=f"https://t.me/{bot_name}?start=pick{message.chat.id}_{selected_model}",
                                ),
                            ],
                            # [
                            #     InlineKeyboardButton(
                            #         text="🔁 Сменить модель",
                            #         callback_data=f"model_change;{selected_model}",
                            #     ),
                            # ],
                        ],
                    ),
                    parse_mode="Markdown",
                )
            else:
                # Send a message indicating that a game is already in progress
                bot.send_message(
                    message.chat.id,
                    "❌ Игра уже идет или вы уже в очереди!",
                    parse_mode="Markdown",
                )
        else:
            # Send a message indicating that the command can only be used in a group chat  # noqa: E501
            bot.send_message(
                message.chat.id,
                "❌ Эту команду можно использовать только в групповом чате!",
            )
    except Exception as e:  # noqa: BLE001
        # Send a message indicating that an error occurred
        bot.send_message(
            message.chat.id,
            f"⛔ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: RUF001, E501
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004


def from_queue_processing(request: tuple) -> None:
    """Process games from queue.

    Parameters
    ----------
    request : tuple
        data tuple

    Returns
    -------
    None

    """
    answer, group_id, dms_id, user_nick, message_queue_id, user_id, selected_model = (
        request
    )

    bot.delete_message(dms_id, message_queue_id)

    games_db.upsert(
        {"id": str(group_id), "data": [answer, {}, "", {}, ""]},
        User.id == str(group_id),
    )

    image_generation = bot.send_message(
        dms_id,
        f'Картинка "*{answer}*" генерируется 😎',
        parse_mode="Markdown",
    )
    status, generated_photo_bytes = (
        kandinsky_client.generate_image(answer)
        if selected_model == "kandinsky"
        else dalle_client.generate_image(answer)
    )

    if status == 200:  # noqa: PLR2004
        database_client.remove_credits_from_user(dms_id, get_price(selected_model))

        sent_image = bot.send_photo(
            group_id,
            generated_photo_bytes,
            f"Пользователь *{user_nick}* загадал слово!\n\nПишите свои догадки в формате `/guess ответ`, `guess ответ` или просто отвечайте на сообщения бота в этом чате!\n\nЧтобы посмотреть топ слов в текущей игре, используйте `/top кол-во` (по умолчанию 5).\n\nЧтобы остановить игру, напишите `/stop`.",  # noqa: RUF001, E501
            parse_mode="Markdown",
        )
        bot.delete_message(dms_id, image_generation.message_id)

        games_db.upsert(
            {
                "id": str(group_id),
                "data": [answer, {}, sent_image.photo[0].file_id, {}, user_id],
            },
            User.id == str(group_id),
        )

        bot.send_message(
            dms_id,
            f'Ваше слово "*{answer}*" успешно загадано! ✅ Перейдите обратно в группу.',
            parse_mode="Markdown",
        )

    else:
        games_db.remove(doc_ids=[games_db.search(User.id == str(group_id))[0].doc_id])
        bot.delete_message(dms_id, image_generation.message_id)
        bot.send_message(
            dms_id,
            "❌ Ошибка генерации. Возможно, ваш запрос содержит недопустимые слова.",
            parse_mode="Markdown",
        )
        bot.send_message(
            group_id,
            "❌ Ошибка генерации. Начните игру заново.",
            parse_mode="Markdown",
        )


def start_word_picking(
    message: telebot.types.Message, group_id: int, selected_model: str,
) -> None:
    """Start word picking.

    Parameters
    ----------
    message : telebot.types.Message
        message
    group_id: int
        id of the group the game will be played in
    selected_model: str
        selected model

    Returns
    -------
    None

    """
    try:
        # Check if a game is already in progress
        if games_db.search(User.id == str(group_id)):
            bot.send_message(message.chat.id, "❌ Игра уже идет или вы уже в очереди!")
        else:  # noqa: PLR5501
            if message.text:
                answer = message.text.strip().lower()
                # Check if the answer is a single word
                if not len(answer.split()) > 1:
                    # Check if the answer contains only English letters
                    if contains_only_english_letters(answer):
                        answer_embedding = embedding_client.get_embedding(answer)
                        # Check if the answer exists in the embeddings
                        if embedding_client.exist(answer_embedding):
                            logging.info(
                                f"Game started | ans: {answer} | g_id: {group_id}",  # noqa: G004
                            )

                            lenght = get_queue_length() + 1

                            games_db.upsert(
                                {"id": str(group_id), "data": [answer, {}, "", {}, ""]},
                                User.id == str(group_id),
                            )

                            wait_time = lenght * delay

                            queue_message = bot.send_message(
                                message.chat.id,
                                "⌛ Вы добавлены в очередь.\nПримерное время ожидания: "  # noqa: RUF001
                                + (
                                    f"*{wait_time // 60}* мин."
                                    if (wait_time // 60) > 0
                                    else f"*{wait_time}* сек."
                                ),
                                parse_mode="Markdown",
                            )

                            add_request_to_queue(
                                answer,
                                group_id,
                                message.chat.id,
                                message.from_user.full_name,
                                queue_message.id,
                                message.from_user.id,
                                logger,
                                selected_model,  # model user selected
                            )

                        else:
                            bot.send_message(
                                message.chat.id,
                                "❌ Такого слова не существует!",
                                reply_markup=InlineKeyboardMarkup(
                                    [
                                        [
                                            InlineKeyboardButton(
                                                text="Загадать заново!",
                                                url=f"https://t.me/{bot_name}?start=pick{group_id}_{selected_model}",
                                            ),
                                        ],
                                    ],
                                ),
                            )
                    else:
                        bot.send_message(
                            message.chat.id,
                            "❌ Слово должно быть английским и состоять только из букв!",  # noqa: E501
                            reply_markup=InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            text="Загадать заново!",
                                            url=f"https://t.me/{bot_name}?start=pick{group_id}_{selected_model}",
                                        ),
                                    ],
                                ],
                            ),
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ Пришли мне слово, а не предложение!",  # noqa: RUF001
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        text="Загадать заново!",
                                        url=f"https://t.me/{bot_name}?start=pick{group_id}_{selected_model}",
                                    ),
                                ],
                            ],
                        ),
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Отправь мне слово, а не картинку/файл/опрос!",  # noqa: RUF001
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text="Загадать заново!",
                                    url=f"https://t.me/{bot_name}?start=pick{group_id}_{selected_model}",
                                ),
                            ],
                        ],
                    ),
                )
    except Exception as e:  # noqa: BLE001
        bot.send_message(
            message.chat.id,
            f"⛔ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: RUF001, E501
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004


@bot.message_handler(commands=["guess"])
def guess(message: Message) -> None:  # noqa: PLR0912, PLR0915, C901
    """Guess word in the group.

    Parameters
    ----------
    message : telebot.types.Message
        message

    Returns
    -------
    None

    """
    try:
        group_id = message.chat.id

        if not games_db.search(User.id == str(group_id)):
            bot.send_message(message.chat.id, "❌ Сейчас не идет никакая игра!")
        else:  # noqa: PLR5501
            if message.chat.type != "private":
                param = get_parameter(message.text)
                if param:
                    if games_db.search(User.id == str(group_id))[0]["data"][2] != "":
                        if contains_only_english_letters(param):
                            given_try = param.lower().strip()
                            correct_answer = (
                                games_db.search(User.id == str(group_id))[0]["data"][0]
                                .lower()
                                .strip()
                            )
                            if correct_answer == given_try:
                                if games_db.search(User.id == str(group_id)):
                                    new_dict = games_db.search(
                                        User.id == str(group_id),
                                    )[0]["data"][3]

                                    new_dict[str(message.from_user.id)] = [
                                        *new_dict.get(str(message.from_user.id), []),
                                        100,
                                    ]

                                    games_db.upsert(
                                        {
                                            "id": str(group_id),
                                            "data": [
                                                correct_answer,
                                                games_db.search(
                                                    User.id == str(group_id),
                                                )[0]["data"][1],
                                                games_db.search(
                                                    User.id == str(group_id),
                                                )[0]["data"][2],
                                                new_dict,
                                                games_db.search(
                                                    User.id == str(group_id),
                                                )[0]["data"][4],
                                            ],
                                        },
                                        User.id == str(group_id),
                                    )
                                    top_final("10", message.chat.id)
                                    scoreboard_final(message.chat.id)
                                    if (
                                        len(
                                            games_db.search(User.id == str(group_id))[
                                                0
                                            ]["data"][3][str(message.from_user.id)],
                                        )
                                        == 1
                                    ):
                                        bot.send_message(
                                            group_id,
                                            f"🎉 *{message.from_user.full_name}*, молодец! Ты отгадал слово *{correct_answer}* с первой попытки! Вот это мастерство! 🤯",  # noqa: E501, RUF001",",
                                            parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(
                                                [
                                                    [
                                                        InlineKeyboardButton(
                                                            text="🎮 Играть снова!",
                                                            callback_data="play",
                                                        ),
                                                    ],
                                                ],
                                            ),
                                        )
                                    else:
                                        bot.send_message(
                                            group_id,
                                            f"🎉 *{message.from_user.full_name}* отгадал слово *{correct_answer}*!",  # noqa: E501,
                                            parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(
                                                [
                                                    [
                                                        InlineKeyboardButton(
                                                            text="🎮 Играть снова!",
                                                            callback_data="play",
                                                        ),
                                                    ],
                                                ],
                                            ),
                                        )
                                    if games_db.search(User.id == str(group_id)):
                                        games_db.remove(
                                            doc_ids=[
                                                games_db.search(
                                                    User.id == str(group_id),
                                                )[0].doc_id,
                                            ],
                                        )

                                    logger.info(f"Game ended | g_id: {group_id}")  # noqa: G004
                                else:
                                    bot.send_message(
                                        message.chat.id,
                                        "❌ Сейчас не идет никакая игра!",
                                    )
                            else:
                                correct_embedding = embedding_client.get_embedding(
                                    correct_answer,
                                )
                                given_try_embedding = embedding_client.get_embedding(
                                    given_try,
                                )

                                logger.info(
                                    f"Get {given_try} from {message.from_user.id} | {group_id}",  # noqa: G004, E501
                                )

                                if embedding_client.exist(given_try_embedding):
                                    div = embedding_client.cosine_similarity(
                                        correct_embedding,
                                        given_try_embedding,
                                    )
                                    bot.send_message(
                                        group_id,
                                        f"*{message.from_user.full_name}* близок к правильному ответу на *{round(div * 100, 2)}%*",  # noqa: E501
                                        parse_mode="Markdown",
                                    )
                                    if games_db.search(User.id == str(group_id)):
                                        new_dict1 = games_db.search(
                                            User.id == str(group_id),
                                        )[0]["data"][1]

                                        new_dict1[given_try] = f"{round(div * 100, 2)}%"

                                        new_dict2 = games_db.search(
                                            User.id == str(group_id),
                                        )[0]["data"][3]

                                        new_dict2[str(message.from_user.id)] = [
                                            *new_dict2.get(
                                                str(message.from_user.id),
                                                [],
                                            ),
                                            round(div * 100, 2),
                                        ]

                                        games_db.upsert(
                                            {
                                                "id": str(group_id),
                                                "data": [
                                                    games_db.search(
                                                        User.id == str(group_id),
                                                    )[0]["data"][0],
                                                    new_dict1,
                                                    games_db.search(
                                                        User.id == str(group_id),
                                                    )[0]["data"][2],
                                                    new_dict2,
                                                    games_db.search(
                                                        User.id == str(group_id),
                                                    )[0]["data"][4],
                                                ],
                                            },
                                            User.id == str(group_id),
                                        )

                                else:
                                    bot.send_message(
                                        message.chat.id,
                                        f"❌ *{message.from_user.full_name}*, такого слова не существует!",  # noqa: E501
                                        parse_mode="Markdown",
                                    )

                        else:
                            bot.send_message(
                                message.chat.id,
                                f"❌ *{message.from_user.full_name}*, отгадка должна быть на английском языке и состоять только из букв!",  # noqa: E501
                                parse_mode="Markdown",
                            )
                    else:
                        bot.send_message(
                            message.chat.id,
                            f"❌ *{message.from_user.full_name}*, не спеши! Картинка еще генерируется, или вы в очереди.",  # noqa: E501
                            parse_mode="Markdown",
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"❌ *{message.from_user.full_name}*, отгадка должна быть одним словом!",  # noqa: E501
                        parse_mode="Markdown",
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Эту команду можно использовать только в групповом чате!",
                )
    except Exception as e:  # noqa: BLE001
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004
        bot.send_message(
            message.chat.id,
            f"⛔ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: RUF001, E501
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["top"])
def top(message: Message) -> None:
    """View top words.

    Parameters
    ----------
    message : telebot.types.Message
        message

    Returns
    -------
    None

    """
    try:
        if games_db.search(User.id == str(message.chat.id)):
            param = get_parameter(message.text)
            if not param:
                param = "5"
            if param.isdigit():
                count = int(param)
                if 1 <= count <= 100:  # noqa: PLR2004
                    prep_val = games_db.search(User.id == str(message.chat.id))[0][
                        "data"
                    ][1]
                    if len(prep_val.keys()) != 0:
                        sorted_words = list(  # noqa: C413
                            sorted(  # noqa: C414
                                list(prep_val.items()),
                                key=lambda x: float(x[1][:-1]),
                                reverse=True,
                            ),
                        )

                        count = (
                            len(sorted_words) if len(sorted_words) < count else count
                        )

                        top = sorted_words[:count]

                        output = ""
                        for i, (word, percentage) in enumerate(top, start=1):
                            output += f"{i}) *{word}*: {percentage}\n"

                        bot.send_message(message.chat.id, output, parse_mode="Markdown")
                        bot.send_photo(
                            message.chat.id,
                            photo=games_db.search(User.id == str(message.chat.id))[0][
                                "data"
                            ][2],
                        )
                    else:
                        bot.send_message(
                            message.chat.id,
                            f"❌ *{message.from_user.full_name}*, никаких отгадок еще нет!",  # noqa: E501
                            parse_mode="Markdown",
                        )

                else:
                    bot.send_message(
                        message.chat.id,
                        f"❌ *{message.from_user.full_name}*, укажите количество слов для вывода от 1 до 100.",  # noqa: E501
                        parse_mode="Markdown",
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    f"❌ *{message.from_user.full_name}*, параметр должен быть числом (от 1 до 100)!",  # noqa: E501
                    parse_mode="Markdown",
                )
        else:
            bot.send_message(
                message.chat.id,
                f"❌ *{message.from_user.full_name}*, игра в данный момент не идет",
                parse_mode="Markdown",
            )
    except Exception as e:  # noqa: BLE001
        bot.send_message(
            message.chat.id,
            f"⛔️ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: E501, RUF001
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004


def top_final(amount: str, group_id: int) -> None:
    """View final top statistics.

    Parameters
    ----------
    amount : str
        amount of words to view (hardcoded: 10)
    group_id: int
        group id

    Returns
    -------
    None

    """
    prep_val = games_db.search(User.id == str(group_id))[0]["data"][1]

    if len(prep_val.keys()) != 0:
        count = int(amount)

        sorted_words = list(  # noqa: C413
            sorted(list(prep_val.items()), key=lambda x: float(x[1][:-1]), reverse=True)  # noqa: C414, COM812
        )

        count = len(sorted_words) if len(sorted_words) < count else count

        top = sorted_words[:count]

        output = "Статистика по словам:\n\n"
        for i, (word, percentage) in enumerate(top, start=1):
            output += f"{i}) *{word}*: {percentage}\n"

        bot.send_message(group_id, output, parse_mode="Markdown")


def scoreboard_final(group_id: int) -> None:
    """View final player's scoreboard.

    Parameters
    ----------
    group_id: int
        group id

    Returns
    -------
    None

    """
    players = games_db.search(User.id == str(group_id))[0]["data"][3]

    output_list = []
    for elem in players.items():
        output_list.append(  # noqa: PERF401
            [
                bot.get_chat_member(group_id, str(elem[0])).user.first_name,
                len(elem[1]),
                sum(elem[1]) / len(elem[1]),
            ],
        )

    output_list.sort(key=lambda x: x[2], reverse=True)

    result = "Статистика по пользователям (количество угадываний, средний показатель совпадения):\n\n"  # noqa: E501

    max_id = max(
        players.keys(),
        key=lambda x: (
            len(bot.get_chat_member(group_id, str(x)).user.first_name)
            + len(str(players[x][0]))
        ),
    )

    max_len = len(bot.get_chat_member(group_id, str(max_id)).user.first_name) + len(
        str(len(players[str(max_id)])),
    )

    for elem in output_list:
        result += f"`{elem[0]}: {' ' * (max_len - len(elem[0]) - len(str(elem[1])))}{elem[1]} | {round(elem[2])}%`\n"  # noqa: E501

    bot.send_message(group_id, result, parse_mode="Markdown")


@bot.message_handler(commands=["stop"])
def stop(message: telebot.types.Message) -> None:
    """Stop the game.

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    try:
        if message.chat.type != "private":
            if games_db.search(User.id == str(message.chat.id)):
                if games_db.search(User.id == str(message.chat.id))[0]["data"][4] != "":
                    if message.from_user.id == int(
                        games_db.search(User.id == str(message.chat.id))[0]["data"][4],
                    ):
                        games_db.remove(
                            doc_ids=[
                                games_db.search(User.id == str(message.chat.id))[
                                    0
                                ].doc_id,
                            ],
                        )
                        bot.send_message(
                            message.chat.id,
                            f"🛑 Игра остановлена! Её остановил *{message.from_user.full_name}*.",  # noqa: E501,
                            parse_mode="Markdown",
                        )
                    else:
                        bot.send_message(
                            message.chat.id,
                            f"❌ *{message.from_user.full_name}*, эту команду может использовать только создатель игры!",  # noqa: E501
                            parse_mode="Markdown",
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"❌ *{message.from_user.full_name}*, игра ещё не запустилась. Вы в очереди.",  # noqa: E501
                        parse_mode="Markdown",
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    f"❌ *{message.from_user.full_name}*, игра в данный момент не идет",
                    parse_mode="Markdown",
                )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Эту команду можно использовать только в групповом чате!",
            )
    except Exception as e:  # noqa: BLE001
        bot.send_message(
            message.chat.id,
            f"⛔️ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: E501, RUF001
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004


@bot.message_handler(commands=["shutdown"])
def shutdown(message: Message) -> None:
    """[admin only] Shutdown the bot.

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    if message.from_user.id in gods:
        restart = bot.send_message(
            message.chat.id,
            "⌛️ Произвожу рестарт...",
        )
        for game in games_db.all():
            game_id = game["id"]
            bot.send_message(
                int(game_id),
                "ℹ️ *Внимание!* ℹ️\n\nСейчас произойдёт запланированный рестарт бота. Ваша игра сохранится. Пожалуйста, подождите. Приносим свои извинения за неудобства.",  # noqa: E501, RUF001
                parse_mode="Markdown",
            )
        bot.delete_message(message.chat.id, restart.message_id)
        logger.info("shutdowned bot")
        bot.send_message(
            message.chat.id,
            "✅ Сообщения отправились успешно!",
        )
        bot.stop_bot()


@bot.message_handler(commands=["models"])
def models(message: Message) -> None:
    """View models and their difference.

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    try:
        photo = open(f"pics/kd{randint(1, 2)}.jpg", "rb")  # noqa: PTH123, SIM115, S311
        bot.send_photo(
            message.chat.id,
            photo,
            """*Разница между DALL-E 3 и Kandinsky*\n\n*DALL-E 3* - это нейросеть, разработанная OpenAI.\n*Kandinsky* - это в свою очередь нейросеть от "Сбера".\nОбе нейросети способны генерировать изображения на основе текстового описания. *DALL-E 3* может создавать более сложные и уникальные изображения, превосходящие возможности обычного рисования или графического дизайна. *Kandinsky* в то время генерирует похожие друг на друга и несложные изображения.""",  # noqa: E501, RUF001
            parse_mode="Markdown",
        )
    except Exception as e:  # noqa: BLE001
        # Send a message indicating that an error occurred
        bot.send_message(
            message.chat.id,
            f"⛔ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: RUF001, E501
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: TRY400, G004


def get_str_token(n: int) -> str:
    """Get string from amount of tokens.

    Parameters
    ----------
    n: int
        amount of tokens

    Returns
    -------
    str
        tokens' form of word

    """
    if n % 10 == 1 and n % 100 != 11:  # noqa: PLR2004
        return "токен"
    if n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):  # noqa: PLR2004
        return "токена"
    return "токенов"


@bot.message_handler(commands=["balance"])
def balance(message: Message) -> None:
    """View balance.

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    try:
        if message.chat.type == "private":
            tokens = database_client.get_user_string_by_id(str(message.from_user.id))[3]

            bot.send_message(
                message.chat.id,
                f"💰 Ваш баланс: *{tokens}* {get_str_token(tokens)}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="➕ Пополнить баланс",  # noqa: RUF001
                                callback_data="add_balance",
                            ),
                        ],
                    ],
                ),
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Эту команду можно использовать только в личных сообщениях!",
            )
    except Exception as e:  # noqa: BLE001
        # Send a message indicating that an error occurred
        bot.send_message(
            message.chat.id,
            f"⛔ Возникла ошибка, пожалуйста, сообщите об этом @FoxFil\n\nОшибка:\n\n`{e}`",  # noqa: E501, RUF001
            parse_mode="Markdown",
        )
        logger.error(f"ERROR: {e}")  # noqa: G004, TRY400


@bot.message_handler(commands=["remove_tokens"])
def handle_remove_tokens(message: Message) -> None:
    """[admin only] Remove tokens from user.

    Usage: /remove_tokens {user_id} {amount}

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    if message.from_user.id in gods:
        _, user_id, amount = message.text.split()
        database_client.remove_credits_from_user(user_id, amount)
        bot.send_message(
            message.chat.id,
            f"токены были списаны. сейчас у юзера {database_client.get_user_string_by_id(str(user_id))[3]} токенов",  # noqa: E501, RUF001
        )


@bot.message_handler(commands=["add_tokens"])
def handle_add_tokens(message: Message) -> None:
    """[admin only] Add tokens to user.

    Usage: /add_tokens {user_id} {amount}

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    if message.from_user.id in gods:
        _, user_id, amount = message.text.split()
        database_client.add_credits_to_user(user_id, amount)
        bot.send_message(
            message.chat.id,
            f"токены были добавлены. сейчас у юзера {database_client.get_user_string_by_id(str(user_id))[3]} токенов",  # noqa: RUF001, E501
        )


@bot.message_handler(content_types=["text"])
def alternative_guess(message: Message) -> None:
    """Alernative to /guess command.

    Parameters
    ----------
    message: telebot.types.Message
        message

    Returns
    -------
    None

    """
    if message.text.lower().startswith("guess") and (
        len(message.text) == 5 or message.text[5] == " "  # noqa: PLR2004
    ):
        message.text = "/" + message.text
        guess(message)
    elif (
        message.reply_to_message
        and message.reply_to_message.from_user.id == bot.get_me().id
    ):
        message.text = "/guess " + message.text
        guess(message)


start_thread(f=from_queue_processing, logger=logger, delay=delay)
logger.info("started bot")
bot.infinity_polling()
