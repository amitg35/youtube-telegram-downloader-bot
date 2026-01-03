import os
import re
import asyncio
import logging
import shutil
import subprocess
from uuid import uuid4

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from yt_dlp import YoutubeDL

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- HELPERS ---------------- #

def is_youtube_url(text: str) -> bool:
    pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/"
    return re.match(pattern, text) is not None


def format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


def get_video_info(url: str) -> dict:
    ydl_opts = {"quiet": True}
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


# ---------------- BOT HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome!*\n\n"
        "Bas YouTube link bhejo 🎥\n"
        "Main tumhe *video & MP3 download options* dunga.\n\n"
        "_Fast • Simple • Free_",
        parse_mode="Markdown"
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not is_youtube_url(url):
        await update.message.reply_text("❌ Valid YouTube link bhejo.")
        return

    try:
        info = get_video_info(url)
    except Exception:
        await update.message.reply_text("❌ Video info fetch nahi ho pa raha.")
        return

    context.user_data["url"] = url

    title = info.get("title")
    duration = format_duration(info.get("duration", 0))
    thumbnail = info.get("thumbnail")

    keyboard = [
        [
            InlineKeyboardButton("🎥 4K", callback_data="2160"),
            InlineKeyboardButton("🎥 1440p", callback_data="1440")
        ],
        [
            InlineKeyboardButton("🎥 1080p", callback_data="1080"),
            InlineKeyboardButton("🎥 720p", callback_data="720")
        ],
        [
            InlineKeyboardButton("🎥 480p", callback_data="480")
        ],
        [
            InlineKeyboardButton("🎧 MP3 320kbps", callback_data="mp3_320"),
            InlineKeyboardButton("🎧 MP3 128kbps", callback_data="mp3_128")
        ]
    ]

    await update.message.reply_photo(
        photo=thumbnail,
        caption=(
            f"*{title}*\n"
            f"⏱ Duration: {duration}\n\n"
            "👇 Quality select karo"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality = query.data
    url = context.user_data.get("url")

    job_id = str(uuid4())
    output_template = f"{DOWNLOAD_DIR}/{job_id}.%(ext)s"

    await query.edit_message_caption("⏬ Download start ho raha hai...")

    try:
        if quality.startswith("mp3"):
            bitrate = "320" if "320" in quality else "128"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }],
                "quiet": True
            }
        else:
            ydl_opts = {
                "format": f"bestvideo[height<={quality}]+bestaudio/best",
                "outtmpl": output_template,
                "merge_output_format": "mp4",
                "quiet": True
            }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for file in os.listdir(DOWNLOAD_DIR):
            if job_id in file:
                path = os.path.join(DOWNLOAD_DIR, file)
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=open(path, "rb"),
                    caption="✅ Download complete!"
                )
                os.remove(path)
                break

    except Exception as e:
        await query.edit_message_caption("❌ Download error aaya.")


# ---------------- MAIN ---------------- #

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(download_callback))

    webhook_url = f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"

    await app.bot.set_webhook(webhook_url)
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url
    )


if __name__ == "__main__":
    asyncio.run(main())
