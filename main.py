import os
import io
import logging
import threading
from flask import Flask
from PIL import Image, ImageDraw
import img2pdf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

# ─── Flask keep-alive for Render Web Service ────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "✅ Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# ─── Image Processing ───────────────────────────────────────────────────────

def add_rounded_corners(img: Image.Image, radius: int = 80) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.paste(img, mask=mask)
    return result


def make_a4_pdf(img: Image.Image) -> io.BytesIO:
    # A4 at 300 DPI = 2480 x 3508 px
    A4_W, A4_H = 2480, 3508

    # Strip metadata by rebuilding pixel data
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    clean = clean.convert("RGB")

    # Fit inside A4 keeping aspect ratio
    clean.thumbnail((A4_W, A4_H), Image.LANCZOS)

    # Center on white A4 canvas
    canvas = Image.new("RGB", (A4_W, A4_H), "white")
    x = (A4_W - clean.width) // 2
    y = (A4_H - clean.height) // 2
    canvas.paste(clean, (x, y))

    # Save as JPEG bytes then wrap in PDF
    jpeg_buf = io.BytesIO()
    canvas.save(jpeg_buf, format="JPEG", quality=95)
    jpeg_buf.seek(0)

    pdf_buf = io.BytesIO()
    pdf_buf.write(img2pdf.convert(jpeg_buf.read()))
    pdf_buf.seek(0)
    return pdf_buf

# ─── Bot Handlers ────────────────────────────────────────────────────────────

KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔵 Rounded Corners", callback_data="rounded"),
        InlineKeyboardButton("📄 A4 PDF",          callback_data="a4pdf"),
    ]
])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to TG Photo Editor!*\n\n"
        "Send me any image and choose:\n\n"
        "🔵 *Rounded Corners* — adds smooth rounded corners\n"
        "📄 *A4 PDF* — strips metadata, resizes to A4, sends as PDF\n\n"
        "_Supports both compressed photos and original files._",
        parse_mode="Markdown"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.photo[-1].file_id
    context.user_data["file_id"] = file_id
    context.user_data["is_doc"] = False
    await update.message.reply_text("What do you want to do with this image?",
                                    reply_markup=KEYBOARD)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        context.user_data["file_id"] = doc.file_id
        context.user_data["is_doc"] = True
        await update.message.reply_text("What do you want to do with this image?",
                                        reply_markup=KEYBOARD)
    else:
        await update.message.reply_text("⚠️ Please send an image file.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    file_id = context.user_data.get("file_id")
    if not file_id:
        await query.edit_message_text("⚠️ Please send an image first.")
        return

    await query.edit_message_text("⏳ Processing your image…")

    try:
        tg_file = await context.bot.get_file(file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)
        img = Image.open(buf)

        if query.data == "rounded":
            result = add_rounded_corners(img, radius=80)
            out = io.BytesIO()
            result.save(out, format="PNG")
            out.seek(0)
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=out,
                filename="rounded_corners.png",
                caption="✅ Rounded corners applied!"
            )

        elif query.data == "a4pdf":
            pdf = make_a4_pdf(img)
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=pdf,
                filename="a4_image.pdf",
                caption="✅ Metadata stripped & converted to A4 PDF!"
            )

        await query.edit_message_text("✅ Done! Send another image anytime.")

    except Exception as e:
        logger.exception("Processing error")
        await query.edit_message_text(f"❌ Error: {e}")

# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")

    # Start Flask in background so Render sees an HTTP server
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot started polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
