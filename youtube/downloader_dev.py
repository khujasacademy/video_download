import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
import instaloader
import yt_dlp
from dotenv import load_dotenv
import shutil
from telethon.errors import RPCError

load_dotenv()

# =================== KONFIGURATSIYA ===================
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'users.db')
INSTA_USERNAME = os.getenv('INSTA_USERNAME')
INSTA_PASSWORD = os.getenv('INSTA_PASSWORD')
SESSION_NAME = os.getenv('SESSION_NAME', 'bot_session')
FFMPEG_PATH = r"C:/ffmpeg/bin/ffmpeg.exe"  # FFmpeg aniq manzili

# Papkani yaratish
os.makedirs('youtube', exist_ok=True)

def adapt_datetime(val):
    """datetime obyektini timestampga aylantirish"""
    return int(val.timestamp())

def convert_datetime(val):
    """Timestampni datetime formatiga o‘tkazish"""
    return datetime.fromtimestamp(int(val))

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)


# =================== INSTAGRAM LOGIN ===================
L = instaloader.Instaloader()
if os.path.exists(SESSION_NAME):
    try:
        L.load_session_from_file(INSTA_USERNAME, filename=SESSION_NAME)
        print("Instagram sessiya yuklandi.")
    except Exception as e:
        print("Sessiyani yuklashda xatolik, qaytadan login qilinmoqda:", str(e))
        L.login(INSTA_USERNAME, INSTA_PASSWORD)
        L.save_session_to_file(SESSION_NAME)
else:
    L.login(INSTA_USERNAME, INSTA_PASSWORD)
    L.save_session_to_file(SESSION_NAME)
    print("Instagram sessiya fayli yaratildi.")

# =================== MA'LUMOTLAR BAZASI ===================
def create_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TEXT,
            last_seen TEXT,
            usage_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def update_user_stats(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        cursor.execute('UPDATE users SET last_seen = ?, usage_count = usage_count + 1 WHERE user_id = ?', (today, user_id))
    else:
        cursor.execute('INSERT INTO users (user_id, first_seen, last_seen, usage_count) VALUES (?, ?, ?, 1)', (user_id, today, today))
    conn.commit()
    conn.close()

# =================== TELEGRAM BOT ===================
bot = TelegramClient(SESSION_NAME, API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    update_user_stats(user_id)
    await event.respond(
        "Salom! Men Instagram va YouTube videolarni yuklab beruvchi botman.\n"
        "Menga video havolasini yuboring, men uni yuklab beraman.",
        buttons=[
            Button.url("Instagram", "https://www.instagram.com"),
            Button.url("YouTube", "https://www.youtube.com"),
        ]
    )
    raise events.StopPropagation

# =================== INSTAGRAM VIDEO YUKLASH ===================
def get_instagram_video(url):
    try:
        post = instaloader.Post.from_shortcode(L.context, url.split('/')[-2])
        return post.video_url if post.is_video else None
    except Exception as e:
        print("Instagram yuklashda xatolik:", str(e))
        return None

# =================== YOUTUBE VIDEO YUKLASH ===================
async def download_youtube_video(url, user_id):
    output_path = f'youtube/{user_id}.mp4'
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': output_path,
        'quiet': True,
        'merge_output_format': 'mp4'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        print(f"YouTube yuklashda xatolik: {str(e)}")
    return None

@bot.on(events.NewMessage)
async def link_handler(event):
    text = event.raw_text.strip()
    user_id = event.sender_id
    update_user_stats(user_id)
    
    youtube_regex = r"(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+)"
    youtube_match = re.search(youtube_regex, text)
    
    if youtube_match:
        url = youtube_match.group(0)
        await event.reply("📥 YouTube video yuklanmoqda...")

        video_path = await download_youtube_video(url, user_id)
        
        if video_path and os.path.exists(video_path):
            try:
                await bot.send_file(user_id, video_path, caption="📹 YouTube video")
                os.remove(video_path)  # Faylni o‘chirish
            except RPCError as e:
                await event.reply(f"⚠️ Videoni yuborishda xatolik: {str(e)}")
        else:
            await event.reply("⚠️ YouTube videoni yuklab bo‘lmadi!")
    else:
        await event.reply("⚠️ Noto'g'ri YouTube havolasi yuborildi.")


if __name__ == "__main__":
    create_database()
    print("Bot ishga tushdi...")
    bot.run_until_disconnected()