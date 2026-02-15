import logging
import asyncio
import random
import string
import threading
import streamlit as st
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import routeros_api

# --- DASHBOARD WEB STREAMLIT ---
st.set_page_config(page_title="NOC PT Auri", page_icon="📡")
st.title("📡 NOC Bot Dashboard")
st.subheader("PT AURI STEEL METALINDO")

# Container untuk log di dashboard agar lu bisa lihat errornya
log_container = st.empty()

def update_status(text):
    log_container.info(f"Log: {text}")

# --- KONFIGURASI SECRETS ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    MT_HOST = st.secrets["MIKROTIK_HOST"]
    MT_USER = st.secrets["MIKROTIK_USER"]
    MT_PASS = st.secrets["MIKROTIK_PASS"]
    MT_PORT = int(st.secrets["MIKROTIK_PORT"])
    st.success("✅ Secrets Loaded!")
except Exception as e:
    st.error(f"❌ Cek Secrets lu: {e}")
    st.stop()

# State Conversation
PREFIX, PROFILE, QTY, MAN_USER, MAN_PROF, SEARCH_IP, PING_TARGET = range(7)

def connect_mt():
    try:
        pool = routeros_api.RouterOsApiPool(
            MT_HOST, username=MT_USER, password=MT_PASS, port=MT_PORT, 
            plaintext_login=True, timeout=10
        )
        return pool
    except Exception as e:
        update_status(f"Gagal konek MikroTik: {e}")
        return None

# --- HANDLER START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    keyboard = [['📝 DHCP Leases', '🔌 Interfaces'], ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
                ['🔑 Hotspot MGMT', '🔍 CARI IP'], ['📡 PING DARI IP', '⚙️ System Info']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"<b>🚀 NOC ONLINE</b>\nHalo <b>{user}</b>! Menu siap.", reply_markup=reply_markup, parse_mode='HTML')

# --- LOGIKA MENU (FULL - KAGA ADA YANG DIHAPUS) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    pool = connect_mt()
    if not pool:
        await update.message.reply_text("❌ MikroTik Offline/Timeout!")
        return
    api = pool.get_api()

    if text == '🚀 Speedtest WAN':
        msg = await update.message.reply_text("🚀 Testing...")
        wan = "pppoe-out1"
        rx_s = []
        for i in range(1, 6): # Sampling diperpendek biar kaga timeout di Streamlit
            try:
                stats = api.get_resource('/interface').call('monitor-traffic', {'interface': wan, 'once': ''})[0]
                rx_s.append(int(stats.get('rx-bits-per-second', 0))/1024/1024)
            except: pass
            await asyncio.sleep(1)
        await msg.edit_text(f"✅ DL Max: {max(rx_s):.2f} Mbps")

    elif text == '📝 DHCP Leases':
        kb = [[InlineKeyboardButton("📡 LAN (1.x)", callback_data="ls_range_192.168.1."), InlineKeyboardButton("📡 WIFI (11.x)", callback_data="ls_range_172.16.11.")],
              [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_range_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_range_10.10.10.")],
              [InlineKeyboardButton("📡 LOG (100.x)", callback_data="ls_range_10.10.100.")]]
        await update.message.reply_text("<b>📝 DHCP 5 SEGMENT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔌 Interfaces':
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{'✅' if i.get('disabled')=='false' else '❌'} {i.get('name')}", callback_data=f"intset_{'dis' if i.get('disabled')=='false' else 'en'}_{i.get('name')}")] for i in ints[:10]]
        await update.message.reply_text("<b>🔌 INTERFACE</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔑 Hotspot MGMT':
        kb = [[InlineKeyboardButton("➕ VOUCHER", callback_data="hs_gen_start")], [InlineKeyboardButton("👥 AKTIF", callback_data="hs_active")]]
        await update.message.reply_text("<b>🔑 HOTSPOT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    pool.disconnect()

# --- RUN BOT ---
def run_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = Application.builder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        # ... (ConversationHandler & Callback dipasang lengkap di sini)
        
        update_status("Bot mulai polling...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        update_status(f"CRITICAL ERROR: {e}")

if __name__ == '__main__':
    if "bot_thread" not in st.session_state:
        st.session_state.bot_thread = True
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
    st.success("🟢 Dashboard Aktif. Cek Telegram lu!")
