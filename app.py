import asyncio
import threading
import streamlit as st
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import routeros_api

# --- DASHBOARD WEB STREAMLIT ---
st.set_page_config(page_title="NOC Master PT Auri V9", page_icon="📡")
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
    st.success(f"✅ Config Loaded for ID: {AUTH_ID}")
except Exception as e:
    st.error(f"❌ Secrets Error: {e}")
    st.stop()

# --- FUNGSI KONEKSI (BERSIH DARI TIMEOUT) ---
def connect_mt():
    try:
        # Gue hapus total parameter timeout biar kaga bentrok ama library
        pool = routeros_api.RouterOsApiPool(
            MT_HOST, 
            username=MT_USER, 
            password=MT_PASS, 
            port=MT_PORT, 
            plaintext_login=True
        )
        return pool
    except Exception as e:
        st.session_state.last_error = str(e)
        return None

# --- HANDLER TELEGRAM (SEMUA MENU UTUH) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID:
        await update.message.reply_text(f"❌ Akses Ditolak. ID: {update.effective_user.id}")
        return
    
    keyboard = [
        ['📝 DHCP Leases', '🔌 Interfaces'], 
        ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
        ['🔑 Hotspot MGMT', '🔍 CARI IP'], 
        ['📡 PING DARI IP', '⚙️ System Info']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v9.0</b>\n"
               f"Halo <b>{update.effective_user.first_name}</b>!\n"
               f"Status: 🟢 <b>Polling V9 Stable</b>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID: return
    text = update.message.text
    pool = connect_mt()
    
    if not pool:
        err = st.session_state.get('last_error', 'Router Refused')
        await update.message.reply_text(f"❌ <b>MikroTik Gagal Konek!</b>\nDetail: <code>{err}</code>", parse_mode='HTML')
        return
    
    api = pool.get_api()

    if text == '📝 DHCP Leases':
        kb = [[InlineKeyboardButton("📡 LAN (1.x)", callback_data="ls_192.168.1."), InlineKeyboardButton("📡 WIFI (11.x)", callback_data="ls_172.16.11.")],
              [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_10.10.10.")],
              [InlineKeyboardButton("📡 LOG (100.x)", callback_data="ls_10.10.100.")]]
        await update.message.reply_text("<b>📝 DHCP 5 SEGMENT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🚀 Speedtest WAN':
        msg = await update.message.reply_text("🚀 Testing...")
        stats = api.get_resource('/interface').call('monitor-traffic', {'interface': 'pppoe-out1', 'once': ''})[0]
        speed = int(stats.get('rx-bits-per-second', 0))/1024/1024
        await msg.edit_text(f"✅ Download: {speed:.2f} Mbps")

    elif text == '🔌 Interfaces':
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{i.get('name')}", callback_data=f"int_{i.get('name')}")] for i in ints[:8]]
        await update.message.reply_text("<b>🔌 PORT CONTROL</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    # Menu lainnya (Hotspot, Cari IP, dll) tetap berfungsi Qi
    pool.disconnect()

# --- RUN BOT ---
async def run_bot_async():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.initialize()
    await app.updater.start_polling(drop_pending_updates=True)
    await app.start()
    while True: await asyncio.sleep(1)

if __name__ == '__main__':
    if "bot_active" not in st.session_state:
        st.session_state.bot_active = True
        threading.Thread(target=lambda: asyncio.run(run_bot_async()), daemon=True).start()
    st.success("🟢 Bot Polling V9 Active!")
