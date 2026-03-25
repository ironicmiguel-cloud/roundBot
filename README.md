# 📸 TG Photo Editor Bot

A Telegram bot that edits your images in two ways:

## ✨ Features

- 🔵 **Rounded Corners** — Adds smooth rounded corners to any image, returns as PNG
- 📄 **A4 PDF** — Strips all metadata, resizes image to A4 size, returns as PDF

## 🚀 How to Use

1. Open the bot on Telegram
2. Send any image (photo or file)
3. Choose what you want:
   - Tap **Rounded Corners** to get a PNG with rounded corners
   - Tap **A4 PDF** to get a clean metadata-free A4 PDF

## 🛠️ Setup on Render

1. Push this repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your GitHub repo
4. Set the following:

| Setting | Value |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |

5. Add Environment Variable:

| Key | Value |
|---|---|
| `BOT_TOKEN` | Your Telegram Bot Token from [@BotFather](https://t.me/BotFather) |

6. Click **Deploy** ✅

## 📦 Dependencies

- `python-telegram-bot`
- `Pillow`
- `img2pdf`
- `flask`
