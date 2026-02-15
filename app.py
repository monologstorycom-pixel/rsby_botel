import asyncio
import random
import string
import threading
import streamlit as st
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import routeros_api

# --- DASHBOARD WEB STREAMLIT ---
st.set_page_config(page_title="NOC Master PT Auri V5", page_icon="📡")
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

# State Conversation
PREFIX, PROFILE, QTY, MAN_USER, MAN_PROF, SEARCH_IP, PING_TARGET = range(7)

def connect_mt():
    try:
        pool = routeros_api.RouterOsApiPool(MT_HOST, username=MT_USER, password=MT_PASS, port=MT_PORT, plaintext_login=True, timeout=10)
        return pool
    except: return None

def generate_code(prefix, length=6):
    chars = string.ascii_letters + string.digits
    return f"{prefix}{''.join(random.choice(chars) for _ in range(length))}"

# --- HANDLER START ---
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
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v5.0</b>\n<b>PT AURI STEEL METALINDO</b>\n"
               f"<code>──────────────────────────────</code>\n"
               f"Halo, <b>{update.effective_user.first_name}</b>!\n"
               f"Status: 🟢 <b>Polling V5 Active</b>\n"
               f"<code>──────────────────────────────</code>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

# --- LOGIKA MENU UTAMA ---
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
              [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_10.10.10.")],
              [InlineKeyboardButton("📡 LOG (100.x)", callback_data="ls_10.10.100.")]]
        await update.message.reply_text("<b>📝 DHCP 5 SEGMENT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🚀 Speedtest WAN':
        msg = await update.message.reply_text("🚀 Testing Jalur Biznet...")
        stats = api.get_resource('/interface').call('monitor-traffic', {'interface': 'pppoe-out1', 'once': ''})[0]
        speed = int(stats.get('rx-bits-per-second', 0))/1024/1024
        await msg.edit_text(f"✅ Current Download: {speed:.2f} Mbps")

    elif text == '🔌 Interfaces':
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{'✅' if i.get('disabled')=='false' else '❌'} {i.get('name')}", callback_data=f"intset_{i.get('name')}")] for i in ints[:8]]
        await update.message.reply_text("<b>🔌 PORT CONTROL</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔑 Hotspot MGMT':
        kb = [[InlineKeyboardButton("➕ VOUCHER", callback_data="hs_gen_start"), InlineKeyboardButton("👥 AKTIF", callback_data="hs_active")]]
        await update.message.reply_text("<b>🔑 HOTSPOT MGMT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '⚙️ System Info':
        res = api.get_resource('/system/resource').call('print')[0]
        await update.message.reply_text(f"CPU: {res.get('cpu-load')}% | Uptime: {res.get('uptime')}", parse_mode='HTML')

    pool.disconnect()

# --- CALLBACKS & CONVERSATIONS ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_ID: return
    query = update.callback_query; await query.answer(); data = query.data.split('_')
    pool = connect_mt(); api = pool.get_api() if pool else None
    if not api: return
    if data[0] == "ls":
        all_l = api.get_resource('/ip/dhcp-server/lease').call('print')
        fil = [l for l in all_l if l.get('address', '').startswith(data[1])]
        msg = f"<b>📝 LEASES: {data[1]}x</b>\n"
        for l in fil[:10]: msg += f"• <code>{l.get('address')}</code> | {l.get('host-name','?')}\n"
        await query.edit_message_text(msg, parse_mode='HTML')
    pool.disconnect()

async def ping_start(u, c): await u.message.reply_text("<b>📡 PING DARI IP:</b>\nSource IP:"); return PING_TARGET
async def do_ping_test(u, c):
    ip = u.message.text; pool = connect_mt(); api = pool.get_api()
    try:
        res = api.get_binary_resource('/').call('ping', {'address': '8.8.8.8', 'src-address': ip, 'count': '5'})
        msg = f"<b>🌐 PING DARI {ip}</b>\n"
        for p in res: msg += f"{'✅' if int(p.get('received',1))>0 else '❌'} <code>{p.get('time','timeout')}</code>\n"
        await u.message.reply_text(msg, parse_mode='HTML')
    finally: pool.disconnect(); return ConversationHandler.END

# --- RUN BOT ASYNC ---
async def run_bot_async():
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📡 PING DARI IP$'), ping_start)],
        states={PING_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_ping_test)]},
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    await app.initialize()
    await app.updater.start_polling(drop_pending_updates=True)
    await app.start()
    while True: await asyncio.sleep(1)

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot_async())

if __name__ == '__main__':
    if "bot_started" not in st.session_state:
        st.session_state.bot_started = True
        threading.Thread(target=start_bot_thread, daemon=True).start()
        st.success("🟢 Bot Polling V5 Active!")
