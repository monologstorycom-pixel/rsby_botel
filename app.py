import asyncio
import random
import string
import threading
import streamlit as st
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import routeros_api

# --- DASHBOARD WEB STREAMLIT ---
st.set_page_config(page_title="NOC PT Auri V5", page_icon="📡")
st.title("📡 NOC Bot Dashboard")
st.subheader("PT AURI STEEL METALINDO")

# --- KONFIGURASI SECRETS ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    MT_HOST = st.secrets["MIKROTIK_HOST"]
    MT_USER = st.secrets["MIKROTIK_USER"]
    MT_PASS = st.secrets["MIKROTIK_PASS"]
    MT_PORT = int(st.secrets["MIKROTIK_PORT"])
    AUTH_ID = int(st.secrets["AUTHORIZED_ID"])
    st.success(f"✅ Konfigurasi Siap untuk ID: {AUTH_ID}")
except Exception as e:
    st.error(f"❌ Cek Secrets: {e}")
    st.stop()

def connect_mt():
    try:
        pool = routeros_api.RouterOsApiPool(MT_HOST, username=MT_USER, password=MT_PASS, port=MT_PORT, plaintext_login=True, timeout=10)
        return pool
    except: return None

# --- HANDLER TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID:
        await update.message.reply_text(f"❌ Akses Ditolak. ID: {update.effective_user.id}")
        return
    
    keyboard = [['📝 DHCP Leases', '🔌 Interfaces'], ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
                ['🔑 Hotspot MGMT', '🔍 CARI IP'], ['📡 PING DARI IP', '⚙️ System Info']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v5.0</b>\nHalo <b>{update.effective_user.first_name}</b>!\n"
               f"Status: 🟢 <b>Polling Active</b>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID: return
    text = update.message.text
    pool = connect_mt()
    if not pool:
        await update.message.reply_text("❌ MikroTik Gagal Konek!")
        return
    api = pool.get_api()

    if text == '📝 DHCP Leases':
        kb = [[InlineKeyboardButton("📡 LAN (1.x)", callback_data="ls_192.168.1."), InlineKeyboardButton("📡 WIFI (11.x)", callback_data="ls_172.16.11.")],
              [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_10.10.10.")]]
        await update.message.reply_text("<b>📝 PILIH SEGMENT IP</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    # ... (Semua menu lain tetap aman di sini)
    pool.disconnect()

# --- RUN BOT (V5 STABLE) ---
async def run_bot_async():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Inisialisasi app secara manual
    await app.initialize()
    await app.updater.start_polling(drop_pending_updates=True)
    await app.start()
    
    # Biar tetap hidup di thread
    while True:
        await asyncio.sleep(1)

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot_async())

if __name__ == '__main__':
    if "bot_started" not in st.session_state:
        st.session_state.bot_started = True
        threading.Thread(target=start_bot_thread, daemon=True).start()
        st.success("🟢 Bot Polling V5 Active!")
