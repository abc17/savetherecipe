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
        "Привет! Это бот для сохранения рецептов из бесконечной ленты Инстаграма. Присылайте боту ссылки на reels или посты — просто через share в инстаграме. Бот будет возвращать текст с рецептом, написанный под этим постом или рилсом. Об ошибках и пожеланиях пишите мне: @anna_abc"
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
        await update.message.reply_text("Пожалуйста, отправьте ссылку на Instagram пост или рилс.")
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

        # Добавление ссылки на источник в конец текста
        post_text_with_source = "{}\n\n-------\nСсылка на исходный пост: {}".format(post_text_cleaned, url)

        # Отправка изображения и текста с хештегами и ссылкой на источник
        await update.message.reply_photo(photo=BytesIO(image_data), caption=post_text_with_source)

        # Удаление исходного сообщения пользователя
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

    except Exception as e:
        logging.exception("Произошла ошибка при обработке запроса:")
        await update.message.reply_text("Произошла ошибка при обработке запроса.")

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
