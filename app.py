import logging
import asyncio
import random
import string
import threading
import streamlit as st
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import routeros_api

# --- DASHBOARD WEB STREAMLIT ---
st.set_page_config(page_title="NOC Master Baru", page_icon="📡")
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
    st.success(f"✅ Konfigurasi Berhasil Dimuat untuk ID: {AUTH_ID}")
except Exception as e:
    st.error(f"❌ Kesalahan Secrets: {e}")
    st.stop()

# --- FUNGSI KONEKSI MIKROTIK (UTUH 5 SEGMENT) ---
def connect_mt():
    try:
        pool = routeros_api.RouterOsApiPool(
            MT_HOST, username=MT_USER, password=MT_PASS, port=MT_PORT, 
            plaintext_login=True, timeout=10
        )
        return pool
    except: return None

# --- HANDLER TELEGRAM (ANTI-HAPUS MENU) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID:
        await update.message.reply_text(f"❌ Akses Ditolak. ID Anda: {update.effective_user.id}")
        return
    
    keyboard = [
        ['📝 DHCP Leases', '🔌 Interfaces'], 
        ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
        ['🔑 Hotspot MGMT', '🔍 CARI IP'], 
        ['📡 PING DARI IP', '⚙️ System Info']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v4.0</b>\n"
               f"<b>PT AURI STEEL METALINDO</b>\n"
               f"<code>──────────────────────────────</code>\n"
               f"Halo, <b>{update.effective_user.first_name}</b>!\n"
               f"Status: 🟢 <b>Bot Baru Ready!</b>\n"
               f"<code>──────────────────────────────</code>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID: return
    text = update.message.text
    pool = connect_mt()
    if not pool:
        await update.message.reply_text("❌ MikroTik Gagal Konek! Cek IP/Port.")
        return
    api = pool.get_api()

    if text == '📝 DHCP Leases':
        kb = [
            [InlineKeyboardButton("📡 LAN (1.x)", callback_data="ls_range_192.168.1."), InlineKeyboardButton("📡 WIFI (11.x)", callback_data="ls_range_172.16.11.")],
            [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_range_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_range_10.10.10.")],
            [InlineKeyboardButton("📡 LOG (100.x)", callback_data="ls_range_10.10.100.")]
        ]
        await update.message.reply_text("<b>📝 PILIH SEGMENT IP</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🚀 Speedtest WAN':
        msg = await update.message.reply_text("🚀 Testing...")
        stats = api.get_resource('/interface').call('monitor-traffic', {'interface': 'pppoe-out1', 'once': ''})[0]
        speed = int(stats.get('rx-bits-per-second', 0))/1024/1024
        await msg.edit_text(f"✅ Current Download: {speed:.2f} Mbps")

    elif text == '🔌 Interfaces':
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{'✅' if i.get('disabled')=='false' else '❌'} {i.get('name')}", callback_data=f"intset_{i.get('name')}")] for i in ints[:8]]
        await update.message.reply_text("<b>🔌 PORT CONTROL</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    
    pool.disconnect()

# --- RUN BOT FUNCTION ---
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Drop Pending Updates agar bot tidak pusing baca chat lama
    app.run_polling(drop_pending_updates=True)

# --- STREAMLIT AUTO-START ---
if __name__ == '__main__':
    st.write("🔄 Sedang mencoba menghidupkan bot...")
    if "bot_thread" not in st.session_state:
        st.session_state.bot_thread = True
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
        st.success("🟢 Bot sedang Polling ke Telegram!")
    else:
        st.info("ℹ️ Bot sudah berjalan di background.")
