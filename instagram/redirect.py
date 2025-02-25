from telethon import TelegramClient, events, Button

# Telegram API configurations
API_ID = 25909676
API_HASH = "b49d57b3f9e5e86753dde2afd7db30b5"
BOT_TOKEN = "7114767996:AAHixgObrEMwihr8MhhalFadC9wZ68xOswg"

# Start the bot with a valid session name
bot = TelegramClient("instagram/instagram_update_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage)
async def handle_message(event):
    try:
        # Message text with Markdown formatting
        message_text = (
            "✅ **Botlarimiz yangilandi!**\n\n"
            "Yangi botlardan foydalanish uchun quyidagi tugmalardan birini tanlang! ⬇️"
        )
        
        # Buttons configuration
        buttons = [
            [Button.url("📱 Instagram Bot", "https://t.me/GetInstaaVideoBot")],
            [Button.url("🎥 YouTube Bot", "https://t.me/GetYouTubeVideoBot")]
        ]
        
        # Send response with buttons
        await event.respond(message_text, buttons=buttons, parse_mode='md')
    
    except Exception as error:
        print(f"Xatolik yuz berdi: {error}")

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    bot.run_until_disconnected()