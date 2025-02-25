import os
import sqlite3
import asyncio
from datetime import datetime
import time
from telethon import TelegramClient, events, Button
import yt_dlp

# 🚀 TELEGRAM BOT CONFIGURATION
API_ID = 25909676
API_HASH = "b49d57b3f9e5e86753dde2afd7db30b5"
BOT_TOKEN = "7921133745:AAGhV7qICLHrq6UCjj18pPgGb7fik_cIOFo"
FFMPEG_PATH = r"C:/ffmpeg/bin/ffmpeg.exe"

bot = TelegramClient("youtube/youtube_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# 📂 DATABASE SETUP
conn = sqlite3.connect("youtube/downloads.db")
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS downloads
             (id INTEGER PRIMARY KEY, 
              user_id INTEGER, 
              video_url TEXT, 
              format TEXT, 
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS video_cache
             (id INTEGER PRIMARY KEY,
              url TEXT,
              format TEXT,
              file_id TEXT,
              user_id INTEGER,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(url, format))''')
conn.commit()

# 📁 DOWNLOAD DIRECTORY
DOWNLOAD_DIR = "youtube/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def format_size(size_bytes):
    """Format file size in MB"""
    return f"{round(size_bytes / (1024 * 1024), 1)}MB" if size_bytes else "Nomaʼlum"

async def clean_old_cache():
    """Clean cache entries older than 30 days"""
    c.execute("DELETE FROM video_cache WHERE timestamp < datetime('now', '-30 days')")
    conn.commit()
    print("✅ Old cache cleaned successfully")

async def periodic_cache_cleaner():
    """Periodic cache cleaning task"""
    while True:
        await clean_old_cache()
        await asyncio.sleep(86400)  # 24 hours

# 🎯 BOT COMMANDS
@bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    buttons = [
        [Button.url("📢 Kanalimiz", "https://t.me/roziboyevdevuz")],
        [Button.url("🧑💻 Dasturchi", "https://t.me/roziboyevdev")]
    ]
    await event.reply("👋 YouTube video yuklovchi botga xush kelibsiz!", buttons=buttons)

@bot.on(events.NewMessage(pattern='/stats'))
async def show_stats(event):
    c.execute("SELECT COUNT(DISTINCT user_id) FROM downloads")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM downloads")
    total_downloads = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM video_cache")
    cached_files = c.fetchone()[0]
    
    stats_msg = (
        f"👥 Foydalanuvchilar: {total_users}\n"
        f"📥 Yuklab olishlar: {total_downloads}\n"
        f"💾 Cache fayllar: {cached_files}"
    )
    await event.reply(stats_msg)

@bot.on(events.NewMessage(pattern="(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"))
async def handle_youtube_link(event):
    user_id = event.sender_id
    url = event.text

    # Save download request
    c.execute("INSERT INTO downloads (user_id, video_url) VALUES (?, ?)", (user_id, url))
    conn.commit()
    request_id = c.lastrowid

    try:
        # Get video info
        ydl_opts = {"quiet": True, "skip_download": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Process info
        title = info.get("title", "Nomaʼlum sarlavha")
        duration = info.get("duration", 0)
        upload_date = info.get("upload_date", "")
        
        if upload_date:
            upload_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%d.%m.%Y")
        
        # Format duration
        hours, rem = divmod(duration, 3600)
        minutes, seconds = divmod(rem, 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

        # Get video formats
        video_formats = {}
        for f in info['formats']:
            if f.get('vcodec') != 'none':
                res = f.get('height')
                if res:
                    if res not in video_formats or f.get('tbr', 0) > video_formats[res].get('tbr', 0):
                        video_formats[res] = f

        # Create buttons
        buttons = []
        for res in sorted(video_formats.keys(), reverse=True):
            f = video_formats[res]
            exact_size = f.get('filesize')
            approx_size = f.get('filesize_approx')
            tbr = f.get('tbr', 0)
            
            if exact_size:
                size = format_size(exact_size)
            elif approx_size:
                size = f"≈{format_size(approx_size)}"
            elif tbr and duration:
                calculated_size = (tbr * 1000 * duration) / (8 * 1024 * 1024)
                size = f"∼{calculated_size:.1f}MB"
            else:
                size = "Nomaʼlum"
            
            buttons.append(Button.inline(f"🎥 {res}p ({size})", data=f"video:{res}:{request_id}"))

        buttons.append(Button.inline("🎧 MP3", data=f"audio:mp3:{request_id}"))

        # Send format options
        msg = (
            f"🎬 **{title}**\n\n"
            f"📅 Yuklangan sana: {upload_date}\n"
            f"⏳ Davomiylik: {duration_str}\n"
            f"🔢 Tanlang:"
        )
        await event.reply(msg, buttons=[buttons[i:i+2] for i in range(0, len(buttons), 2)])

    except Exception as e:
        await event.reply(f"🚫 Xatolik: {str(e)}")

@bot.on(events.CallbackQuery)
async def handle_callback(event):
    data = event.data.decode().split(":")
    request_type = data[0]
    format = data[1]
    request_id = data[2]

    # Original URL ni olish
    c.execute("SELECT video_url FROM downloads WHERE id=?", (request_id,))
    url = c.fetchone()[0]
    user_id = event.sender_id

    # Cache ni tekshirish
    c.execute("SELECT file_id FROM video_cache WHERE url=? AND format=?", (url, format))
    cache_entry = c.fetchone()
    
    if cache_entry:
        file_id = cache_entry[0]
        await event.edit("♻️ Fayl yuborilmoqda...")
        await bot.send_file(event.chat_id, file_id, 
                            print(f"Cache video yubotildi:{user_id}"),
                          caption="✅ @GetYouTubeVideoBot orqali yuklandi!\n\n📥 Instagram video yuklovchi: @GetInstaaVideoBot",
                          supports_streaming=True)
        c.execute("UPDATE video_cache SET timestamp=CURRENT_TIMESTAMP WHERE url=? AND format=?", (url, format))
        conn.commit()
        return

    try:
        # Progress hook funksiyasi
        async def progress_hook(info):
            if info['status'] == 'downloading':
                # Ma'lumotlarni xavfsiz olish
                downloaded = info.get('downloaded_bytes', 0)
                total = info.get('total_bytes') or info.get('total_bytes_estimate', 0)
                speed = info.get('speed', 0)
                eta = info.get('eta', 0)

                # Foizni hisoblash
                try:
                    percent = (downloaded / total * 100) if total > 0 else 0
                except:
                    percent = 0

                # Progress bar (20 qismli)
                filled = int(percent // 5)
                empty = 20 - filled

                # Hajmni formatlash
                def format_size(size):
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if abs(size) < 1024.0:
                            return f"{size:.1f}{unit}"
                        size /= 1024.0
                    return f"{size:.1f}GB"

                # Vaqtni formatlash
                def format_time(seconds):
                    return f"{seconds//3600:02}:{(seconds//60)%60:02}:{seconds%60:02}" if seconds > 0 else "00:00"

                # Xabar tuzish
                progress_msg = (
                    f"📥 Yuklanmoqda...\n"
                    f"▰{'▰' * filled}{'▱' * empty}\n"
                    f"├ {percent:.1f}% tugallandi\n"
                    f"├ {format_size(downloaded)} / {format_size(total)}\n"
                    f"├ Tezlik: {format_size(speed)}/s\n"
                    f"└ Qolgan vaqt: {format_time(eta)}"
                )

                # Xabarni yangilash (3 soniyada 1 marta yoki 2% o'zgarishda)
                last_update = getattr(progress_hook, 'last_update', 0)
                last_percent = getattr(progress_hook, 'last_percent', 0)
                
                if (time.time() - last_update > 3) or (abs(percent - last_percent) >= 2):
                    try:
                        await event.edit(progress_msg)
                        progress_hook.last_update = time.time()
                        progress_hook.last_percent = percent
                    except Exception as e:
                        print(f"Xabar yangilashda xato: {e}")

        # Yuklab olish parametrlari
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
            'ffmpeg_location': FFMPEG_PATH,
            'postprocessor_args': ['-preset', 'fast'],
            'merge_output_format': 'mp4',
            'progress_hooks': [lambda info: asyncio.create_task(progress_hook(info))],
            'noprogress': False,
            'ignoreerrors': True,
            'retries': 3,
            'socket_timeout': 30,
            'http_chunk_size': 1048576,
            'verbose': False
        }

        if request_type == "video":
            ydl_opts['format'] = f'bestvideo[height={format}]+bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        else:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320'
            }]

        # Yuklab olishni boshlash
        await event.edit("⏳ Yuklash boshlandi...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if request_type == "audio":
                filename = filename.replace(".webm", ".mp3").replace(".m4a", ".mp3")

        # Faylni yuborish
        await event.edit("📤 Yuklash tugadi! Fayl yuborilmoqda...")
        sent_msg = await bot.send_file(
            event.chat_id, 
            filename, 
            caption="✅ @GetYouTubeVideoBot orqali yuklandi!\n\n📥 Instagram video yuklovchi: @GetInstaaVideoBot",
            supports_streaming=True
        )

        # Cache ga saqlash
        c.execute("""
            INSERT OR REPLACE INTO video_cache 
            (url, format, file_id, user_id, timestamp) 
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (url, format, sent_msg.file.id, user_id))
        conn.commit()

    except Exception as e:
        await event.respond(f"🚫 Xatolik: {str(e)}")
    finally:
        if 'filename' in locals() and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                print(f"❌ Faylni o'chirishda xatolik: {e}")


if __name__ == "__main__":
    print("🤖 Bot muvaffaqiyatli ishga tushirildi!")
    bot.loop.create_task(periodic_cache_cleaner())
    bot.run_until_disconnected()