import os
import asyncio
from threading import Thread
from io import BytesIO

from PIL import Image, ImageDraw
import img2pdf
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running!", 200


# ── helpers ──────────────────────────────────────────────────────────────────

def add_rounded_corners(img: Image.Image, radius: int = 60) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def image_to_a4_pdf(img: Image.Image) -> bytes:
    # Strip metadata by re-creating image from pixel data
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))

    # A4 at 150 dpi  →  1240 × 1754 px
    clean = clean.resize((1240, 1754), Image.LANCZOS)

    buf = BytesIO()
    clean.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return img2pdf.convert(buf.read())


# ── handlers ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me any image and I'll give you options to edit it!"
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # Accept both compressed photos and files
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await message.reply_text("Please send an image (photo or image file).")
        return

    context.user_data["file_id"] = file_id

    keyboard = [
        [
            InlineKeyboardButton("🔵 Rounded Corners", callback_data="rounded"),
            InlineKeyboardButton("📄 A4 PDF", callback_data="a4pdf"),
        ]
    ]
    await message.reply_text(
        "What would you like to do with this image?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    file_id = context.user_data.get("file_id")
    if not file_id:
        await query.message.reply_text("Please send an image first.")
        return

    await query.message.reply_text("⏳ Processing…")

    tg_file = await context.bot.get_file(file_id)
    buf = BytesIO()
    await tg_file.download_to_memory(buf)
    buf.seek(0)
    img = Image.open(buf)

    if query.data == "rounded":
        result_img = add_rounded_corners(img)
        out = BytesIO()
        result_img.save(out, format="PNG")
        out.seek(0)
        await query.message.reply_document(document=out, filename="rounded.png")

    elif query.data == "a4pdf":
        pdf_bytes = image_to_a4_pdf(img)
        out = BytesIO(pdf_bytes)
        out.seek(0)
        await query.message.reply_document(document=out, filename="image_a4.pdf")


# ── entry point ───────────────────────────────────────────────────────────────

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


async def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image)
    )
    application.add_handler(CallbackQueryHandler(handle_callback))

    await application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")

    # Flask runs in a background daemon thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Bot runs in the main thread with a proper asyncio event loop
    asyncio.run(run_bot())
