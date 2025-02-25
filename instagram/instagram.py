import os
import asyncio
import time
import yt_dlp
import aiohttp
import aiosqlite
from telethon import TelegramClient, events, Button
from telethon.tl.types import Document, DocumentAttributeVideo

# Sozlamalar
API_ID = 25909676
API_HASH = 'b49d57b3f9e5e86753dde2afd7db30b5'
BOT_TOKEN = '7615676303:AAGAHcKUFhTSu0l26r27i2pF4RYRTNJAwJk'
TEMP_DIR = "instagram/temp_downloads"
DB_PATH = "instagram/video_cache.db"
SESSION_PATH = "instagram/bot_session"

# Yuklab olish parametrlari
ydl_opts = {
    'format': 'best',
    'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
    'quiet': True,
    'ignoreerrors': True,
    'noprogress': False,
    'extractor_args': {
        'instagram': {
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Cookie': 'ig_nrcb=1'
            }
        }
    }
}

# SQLite bazasini ishga tushirish
async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS video_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                file_id TEXT NOT NULL,
                user_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

# Foydalanuvchini kuzatish
async def track_user(event):
    user = event.sender
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, last_active)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user.id, user.username, user.first_name, user.last_name))
        await db.commit()

# Statistika ma'lumotlari
async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM video_cache")
        total_cache = (await cursor.fetchone())[0]
        
        return total_users, total_cache

# URLni to'g'rilash
async def resolve_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True) as resp:
                return str(resp.url)
    except Exception as e:
        print(f"URL xatosi: {e}")
        return None

# Keshlangan videoni tekshirish
async def check_cache(url):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT file_id FROM video_cache WHERE url=?", (url,))
        result = await cursor.fetchone()
        return result[0] if result else None

# Yangi video keshlash
async def save_to_cache(url, file_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO video_cache (url, file_id, user_id) VALUES (?, ?, ?)",
            (url, str(file_id), user_id)
        )
        await db.commit()
        
# Eski keshlarni tozalash
async def clean_old_cache():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM video_cache WHERE timestamp < datetime('now', '-3 days')")
        await db.commit()

# Yuklash progressi
async def progress_callback(current, total, event, start_time, progress_msg):
    percent = current / total * 100
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    progress_text = (
        f"📤 Yuklanmoqda...\n"
        f"▰ {'▰' * int(percent // 10)}{'▱' * (10 - int(percent // 10))}\n"
        f"├ {percent:.1f}%\n"
        f"├ {current//1024**2}MB / {total//1024**2}MB\n"
        f"└ Qolgan vaqt: {int(eta // 60):02d}:{int(eta % 60):02d}"
    )
    
    try:
        await event.client.edit_message(
            progress_msg.chat_id,
            progress_msg.id,
            progress_text
        )
    except:
        pass

# Xavfsiz fayl o'chirish
async def safe_delete(path):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
                break
        except PermissionError:
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Fayl o'chirishda xato: {e}")
            break

# Start handler
@events.register(events.NewMessage(pattern='/start'))
async def start_handler(event):
    print(f"/start bosdi: {event.sender.id}")
    await track_user(event)
    buttons = [
        [Button.url("📢 Kanalimiz", "https://t.me/roziboyevdevuz")],
        [Button.url("🧑💻 Dasturchi", "https://t.me/roziboyevdev")],
    ]
    await event.reply(
        "👋 Instagram va TikTok video yuklovchi botga xush kelibsiz!\n\n"
        "📎 Video linkini yuboring va men uni sizga yuklab beraman!",
        buttons=buttons
    )

# Stats handler
@events.register(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    total_users, total_cache = await get_stats()
    await event.reply(
        f"📊 Bot statistikasi:\n\n"
        f"👥 Umumiy foydalanuvchilar: {total_users}\n"
        f"💾 Keshlangan videolar: {total_cache}"
    )

# Asosiy video handler
@events.register(events.NewMessage(incoming=True))
async def video_handler(event):
    if event.text.startswith('/'):
        return
    
    await track_user(event)
    url = event.text.strip()
    
    try:
        # URLni tekshirish
        final_url = await resolve_url(url)
        if not final_url:
            raise ValueError("❌ Noto'g'ri URL formati")
        
        if "instagram.com" not in final_url and "tiktok.com" not in final_url:
            raise ValueError("❌ Faqat Instagram va TikTok linklari")

        # Keshlangan kontentni tekshirish
        cached_file_id = await check_cache(final_url)
        if cached_file_id:
            try:
                await event.reply("♻️ Video yuklanmoqda...")
                await event.client.send_file(
                    event.chat_id, 
                    cached_file_id,
                    caption="✅ @GetInstaaVideoBot orqali yuklandi!\n\n📥 Instagram video yuklovchi: @GetYouTubeVideoBot",
    supports_streaming=True,
    force_document=False,
                    )
                return
            except:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("DELETE FROM video_cache WHERE url=?", (final_url,))
                    await db.commit()

        # Yuklash jarayoni
        progress_msg = await event.reply("⏳ Video yuklanmoqda...")
        start_time = time.time()
        
        # Videoni yuklab olish
        loop = asyncio.get_running_loop()
        video_path = await loop.run_in_executor(None, lambda: download_video(final_url))

        # Faylni tekshirish
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            raise ValueError("❌ Yuklangan fayl topilmadi")

        # Videoni yuborish
        message = await event.client.send_file(
    event.chat_id,
    video_path,
    force_document=False,
    caption="✅ @GetInstaaVideoBot orqali yuklandi!\n\n📥 Instagram video yuklovchi: @GetYouTubeVideoBot",
    supports_streaming=True,
    attributes=[
        DocumentAttributeVideo(
            duration=0, 
            w=0, 
            h=0, 
            supports_streaming=True
        )
    ],
    progress_callback=lambda c, t: progress_callback(c, t, event, start_time, progress_msg)
)

        # File ID ni olish
        if message.file:
            file_id = message.file.id
        elif message.document:
            file_id = message.document.id
        else:
            raise ValueError("❌ File ID aniqlanmadi")

        await save_to_cache(final_url, file_id, event.sender_id)
        await progress_msg.delete()

    except Exception as e:
        await event.reply(f"⚠️ Xatolik: {str(e)}")
    finally:
        if 'video_path' in locals():
            await safe_delete(video_path)

# Yuklash funksiyasi
def download_video(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        raise Exception(f"Yuklab olishda xato: {str(e)}")

# Avto-tozalash
async def auto_clean_task():
    while True:
        await clean_old_cache()
        await asyncio.sleep(3600 * 1000)  # Har 1000 soatda

# Asosiy funksiya
async def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    
    await init_db()
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    client.add_event_handler(start_handler)
    client.add_event_handler(stats_handler)
    client.add_event_handler(video_handler)
    
    asyncio.create_task(auto_clean_task())
    
    print("✅ Bot muvaffaqiyatli ishga tushirildi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())