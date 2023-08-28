import logging
import re
import instaloader
import requests
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import sentry_sdk
import os
from dotenv import load_dotenv

# Загрузка переменных среды из файла .env
load_dotenv(dotenv_path=".env")

# Получение значения токена из переменной среды
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

SENTRY_DSN = os.getenv("SENTRY_DSN")

sentry_sdk.init(
  dsn=SENTRY_DSN,

  # Set traces_sample_rate to 1.0 to capture 100%
  # of transactions for performance monitoring.
  # We recommend adjusting this value in production.
  traces_sample_rate=0
)

# Get instance
L = instaloader.Instaloader()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Включение подробного логирования
logging.basicConfig(level=logging.DEBUG)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    # user = update.effective_user
    await update.message.reply_text(
        "Отправьте первую ссылку, чтобы посмотреть, как это работает. \n\nНапример, эту: https://www.instagram.com/reel/Cr0g43KIznu/?igshid=MTc4MmM1YmI2Ng%3D%3D",
        disable_web_page_preview=True
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Если что-то не работает, есть вопросы или предложения по работе бота - напишите мне @anna_abc")

# async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#   """Echo the user message."""
#  await update.message.reply_text(update.message.text)

async def handle_message(update, context):
    chat_id = update.message.chat_id
    url = update.message.text

    # Регулярное выражение для ссылок с параметром igshid и без него
    pattern_with_igshid = r'/([^/?]+)/\??igshid='
    pattern_without_igshid = r'/([^/?]+)/?$'

    shortcode_with_igshid = re.search(pattern_with_igshid, url)
    shortcode_without_igshid = re.search(pattern_without_igshid, url)

    if shortcode_with_igshid:
        shortcode = shortcode_with_igshid.group(1)
    elif shortcode_without_igshid:
        shortcode = shortcode_without_igshid.group(1)
    else:
        await update.message.reply_text("Пожалуйста, отправьте ссылку пост или рилс в Instagram .")
        return

    try:
        # Извлечение текста и URL изображения из Instagram (для постов и рилс)
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        post_text = post.caption
        image_url = post.url

        # Загрузка бинарных данных изображения
        response = requests.get(image_url)
        image_data = response.content

        # Удаление хештегов в тексте + trim текста
        post_text_cleaned = re.sub(r'#\w+\s*', '', post_text).strip()

        # Разбиение текста на части, если его длина превышает max_message_length
        max_message_length = 900
        text_parts = [post_text_cleaned[i:i + max_message_length] for i in
                      range(0, len(post_text_cleaned), max_message_length)]

        # Проверка, нужно ли разбивать сообщение
        if len(text_parts) == 1:
            # Подготовка подписи с текстом и изображением
            post_text_with_image = "{}\n\n---\nИсточник: {}".format(text_parts[0], url)
            await update.message.reply_photo(photo=BytesIO(image_data), caption=post_text_with_image)
        else:
            # Отправка текста с изображением в первом сообщении
            post_text_with_image = "{}".format(text_parts[0])
            await update.message.reply_photo(photo=BytesIO(image_data), caption=post_text_with_image)

            # Отправка оставшегося текста (без изображения) с отключением предварительного просмотра ссылок
            for text_part in text_parts[1:]:
                post_text_with_source = "{}\n\n-------\nИсточник: {}".format(text_part, url)
                await update.message.reply_text(post_text_with_source, disable_web_page_preview=True)

        # Удаление исходного сообщения пользователя
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)


    except Exception as e:
        logging.exception("Произошла ошибка при обработке запроса:")
        await update.message.reply_text("Произошла ошибка. Проверьте, что ссылка ведет на пост или рилс в Instagram. К сожалению, ссылки из других сервисов бот пока не распознает.")

def main() -> None:
    """Start the bot."""

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - ask for link to inst and download it to the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
