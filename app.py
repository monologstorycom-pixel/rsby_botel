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
st.set_page_config(page_title="NOC Master PT Auri", page_icon="📡")
st.title("📡 NOC Bot Dashboard")
st.subheader("PT AURI STEEL METALINDO")

# --- KONFIGURASI SECRETS ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    MT_HOST = st.secrets["MIKROTIK_HOST"]
    MT_USER = st.secrets["MIKROTIK_USER"]
    MT_PASS = st.secrets["MIKROTIK_PASS"]
    MT_PORT = int(st.secrets["MIKROTIK_PORT"])
    # Masukkan Chat ID kamu di Secrets Streamlit dengan nama "AUTHORIZED_ID"
    AUTH_ID = int(st.secrets["AUTHORIZED_ID"]) 
    st.success("✅ Secrets & Whitelist Loaded!")
except Exception as e:
    st.error(f"❌ Cek Secrets: AUTHORIZED_ID ({MT_PORT}) atau TOKEN mungkin salah!")
    st.stop()

# State Conversation
PREFIX, PROFILE, QTY, MAN_USER, MAN_PROF, SEARCH_IP, PING_TARGET = range(7)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def connect_mt():
    try:
        pool = routeros_api.RouterOsApiPool(
            MT_HOST, username=MT_USER, password=MT_PASS, port=MT_PORT, 
            plaintext_login=True, timeout=15
        )
        return pool
    except: return None

def generate_code(prefix, length=6):
    chars = string.ascii_letters + string.digits
    return f"{prefix}{''.join(random.choice(chars) for _ in range(length))}"

# --- HANDLER START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Validasi ID agar hanya kamu yang bisa akses
    if update.effective_user.id != AUTH_ID:
        await update.message.reply_text(f"❌ Akses Ditolak. ID anda: {update.effective_user.id}")
        return

    user_name = update.effective_user.first_name
    keyboard = [
        ['📝 DHCP Leases', '🔌 Interfaces'], 
        ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
        ['🔑 Hotspot MGMT', '🔍 CARI IP'], 
        ['📡 PING DARI IP', '⚙️ System Info']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v3.1</b>\n"
               f"<b>PT AURI STEEL METALINDO</b>\n"
               f"<code>──────────────────────────────</code>\n"
               f"Halo, <b>{user_name}</b>!\n"
               f"Status: 🟢 <b>Koneksi Privat Aktif</b>\n"
               f"<code>──────────────────────────────</code>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

# --- LOGIKA MENU UTAMA ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID: return # Lock ID
    
    text = update.message.text
    pool = connect_mt()
    if not pool:
        await update.message.reply_text("❌ <b>MikroTik Offline!</b> Cek Port API di Winbox.", parse_mode='HTML')
        return
    api = pool.get_api()

    if text == '🚀 Speedtest WAN':
        sent_msg = await update.message.reply_text("🚀 <b>Testing Biznet (PPPoE)...</b>", parse_mode='HTML')
        wan, rx_s = "pppoe-out1", []
        for i in range(1, 11):
            try:
                stats = api.get_resource('/interface').call('monitor-traffic', {'interface': wan, 'once': ''})[0]
                rx_s.append(int(stats.get('rx-bits-per-second', 0))/1024/1024)
                await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_msg.message_id, text=f"🚀 <b>Loading... {i*10}%</b>", parse_mode='HTML')
            except: pass
            await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_msg.message_id, text=f"<b>✅ DL Max: {max(rx_s):.2f} Mbps</b>", parse_mode='HTML')

    elif text == '📝 DHCP Leases':
        kb = [[InlineKeyboardButton("📡 LAN (1.x)", callback_data="ls_range_192.168.1."), InlineKeyboardButton("📡 WIFI (11.x)", callback_data="ls_range_172.16.11.")],
              [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_range_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_range_10.10.10.")],
              [InlineKeyboardButton("📡 LOG (100.x)", callback_data="ls_range_10.10.100.")]]
        await update.message.reply_text("<b>📝 DHCP 5 SEGMENT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔌 Interfaces':
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{'✅' if i.get('disabled')=='false' else '❌'} {i.get('name')}", callback_data=f"intset_{'dis' if i.get('disabled')=='false' else 'en'}_{i.get('name')}")] for i in ints[:10]]
        await update.message.reply_text("<b>🔌 INTERFACE CONTROL</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    pool.disconnect()

# --- CALLBACK HANDLER ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID: return # Lock ID
    query = update.callback_query; await query.answer(); data = query.data.split('_')
    pool = connect_mt(); api = pool.get_api() if pool else None
    if not api: return

    if data[0] == "ls":
        all_l = api.get_resource('/ip/dhcp-server/lease').call('print')
        fil = [l for l in all_l if l.get('address', '').startswith(data[2])]
        msg = f"<b>📝 LEASES: {data[2]}x</b>\n"
        for l in fil[:10]: msg += f"• {l.get('address')} | {l.get('host-name','?')}\n"
        await query.edit_message_text(msg, parse_mode='HTML')
    pool.disconnect()

# --- RUN BOT ---
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    if "bot_active" not in st.session_state:
        st.session_state.bot_active = True
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
    st.write("🟢 Server Privat Aktif. Gunakan ID Anda untuk akses.")
