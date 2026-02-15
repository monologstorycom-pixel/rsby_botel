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
st.set_page_config(page_title="NOC Bot Dashboard", page_icon="📡")
st.title("📡 NOC Bot Server")
st.subheader("PT AURI STEEL METALINDO")

# --- KONFIGURASI AMAN (MENGAMBIL DARI SECRETS) ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    MT_HOST = st.secrets["MIKROTIK_HOST"]
    MT_USER = st.secrets["MIKROTIK_USER"]
    MT_PASS = st.secrets["MIKROTIK_PASS"]
    MT_PORT = int(st.secrets["MIKROTIK_PORT"])
    st.success("✅ Konfigurasi Secrets Berhasil Dimuat")
except Exception as e:
    st.error("❌ Secrets Error: Pastikan TELEGRAM_TOKEN, MIKROTIK_HOST, dll sudah diisi di Dashboard Streamlit!")
    st.stop()

# State Conversation
PREFIX, PROFILE, QTY = range(3)
MAN_USER, MAN_PROF = range(3, 5)
SEARCH_IP, PING_TARGET = 5, 6

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def connect_mt():
    try:
        pool = routeros_api.RouterOsApiPool(MT_HOST, username=MT_USER, password=MT_PASS, port=MT_PORT, plaintext_login=True)
        return pool
    except: return None

def generate_code(prefix, length=6):
    chars = string.ascii_letters + string.digits
    return f"{prefix}{''.join(random.choice(chars) for _ in range(length))}"

# --- HANDLER TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [['📝 DHCP Leases', '🔌 Interfaces'], ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
                ['🔑 Hotspot MGMT', '🔍 CARI IP'], ['📡 PING DARI IP', '⚙️ System Info']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v3.0</b>\n<b>PT AURI STEEL METALINDO</b>\n"
               f"<code>──────────────────────────────</code>\n"
               f"Halo, <b>{user_name}</b>!\nNode: 🖥️ <b>RB450Gx4 (Streamlit)</b>\n"
               f"Status: 🟢 <b>Semua Fitur Aktif</b>\n"
               f"<code>──────────────────────────────</code>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    pool = connect_mt()
    if not pool: return
    api = pool.get_api()

    if text == '🔌 Interfaces':
        kb = [[InlineKeyboardButton("👁️ VIEW STATUS", callback_data="int_view"), 
               InlineKeyboardButton("⚙️ MANAGE PORT", callback_data="int_manage")]]
        await update.message.reply_text("<b>🔌 INTERFACE MENU</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🚀 Speedtest WAN':
        sent_msg = await update.message.reply_text("🚀 <b>Speedtest PPPoE (Biznet)...</b>", parse_mode='HTML')
        wan, rx_s, tx_s = "pppoe-out1", [], []
        for i in range(1, 11):
            stats = api.get_resource('/interface').call('monitor-traffic', {'interface': wan, 'once': ''})[0]
            rx_s.append(int(stats.get('rx-bits-per-second', 0))/1024/1024)
            tx_s.append(int(stats.get('tx-bits-per-second', 0))/1024/1024)
            await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_msg.message_id, 
                                              text=f"🚀 <b>Test Jalur... {i*10}%</b>", parse_mode='HTML')
            await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_msg.message_id, 
            text=f"<b>✅ SPEEDTEST SELESAI</b>\nDL: <b>{max(rx_s):.2f} Mbps</b>\nUL: <b>{max(tx_s):.2f} Mbps</b>", parse_mode='HTML')

    elif text == '📝 DHCP Leases':
        kb = [[InlineKeyboardButton("📡 1.x (LAN)", callback_data="ls_range_192.168.1."), InlineKeyboardButton("📡 11.x (WIFI)", callback_data="ls_range_172.16.11.")],
              [InlineKeyboardButton("📡 50.x (CCTV)", callback_data="ls_range_192.168.50."), InlineKeyboardButton("📡 10.x (PUBLIC)", callback_data="ls_range_10.10.10.")],
              [InlineKeyboardButton("📡 100.x (LOGIN)", callback_data="ls_range_10.10.100.")]]
        await update.message.reply_text("<b>📝 DHCP LEASES (5 SEGMENT)</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔑 Hotspot MGMT':
        kb = [[InlineKeyboardButton("➕ GEN VOUCHER", callback_data="hs_gen_start"), InlineKeyboardButton("👤 ADD MANUAL", callback_data="hs_man_start")],
              [InlineKeyboardButton("👥 USER AKTIF", callback_data="hs_active")]]
        await update.message.reply_text("<b>🔑 HOTSPOT MGMT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🛡️ Queues Limit':
        queues = api.get_resource('/queue/simple').call('print')
        msg = "<b>🛡️ BANDWIDTH CONTROL</b>\n"
        for q in queues[:10]: msg += f"• {q.get('name')}: {q.get('max-limit')}\n"
        await update.message.reply_text(msg, parse_mode='HTML')

    elif text == '⚙️ System Info':
        res = api.get_resource('/system/resource').call('print')[0]
        msg = f"<b>⚙️ INFO SYSTEM</b>\nCPU: {res.get('cpu-load')}% \nUptime: {res.get('uptime')}"
        await update.message.reply_text(msg, parse_mode='HTML')
    pool.disconnect()

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); data = query.data.split('_')
    pool = connect_mt(); api = pool.get_api()
    if query.data == "int_view":
        ints = api.get_resource('/interface').call('print')
        msg = "<b>👁️ STATUS PORT</b>\n"
        for i in ints: msg += f"• <code>{i.get('name'):<10}</code>: {'✅' if i.get('disabled')=='false' else '❌'}\n"
        await query.edit_message_text(msg, parse_mode='HTML')
    elif query.data == "int_manage":
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{'✅' if i.get('disabled')=='false' else '❌'} {i.get('name')}", callback_data=f"intset_{'dis' if i.get('disabled')=='false' else 'en'}_{i.get('name')}")] for i in ints[:10]]
        await query.edit_message_text("<b>⚙️ MANAGE PORTS</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    elif data[0] == "intset":
        api.get_resource('/interface').call('set', {'numbers': data[2], 'disabled': ('yes' if data[1]=='dis' else 'no')})
        await query.edit_message_text(f"✅ Port <b>{data[2]}</b> Updated!", parse_mode='HTML')
    elif data[0] == "ls":
        all_l = api.get_resource('/ip/dhcp-server/lease').call('print')
        fil = [l for l in all_l if l.get('address', '').startswith(data[2])]
        msg = f"<b>📝 LEASES: {data[2]}x</b>\n"
        for l in fil[:10]: msg += f"• <code>{l.get('address')}</code> | {l.get('host-name','?')}\n"
        await query.edit_message_text(msg, parse_mode='HTML')
    elif query.data == "hs_active":
        active = api.get_resource('/ip/hotspot/active').call('print')
        msg = "<b>👥 AKTIF</b>\n"
        for u in active[:10]: msg += f"• {u.get('user')}\n"
        await query.edit_message_text(msg, parse_mode='HTML')
    pool.disconnect()

# --- CONVERSATIONS ---
async def search_ip_start(u, c): await u.message.reply_text("<b>🔍 CARI IP:</b>"); return SEARCH_IP
async def do_search_ip(u, c):
    q = u.message.text; pool = connect_mt(); api = pool.get_api()
    res = [l for l in api.get_resource('/ip/dhcp-server/lease').call('print') if q in l.get('address','')]
    msg = f"<b>🔎 HASIL: {q}</b>\n"
    for r in res[:5]: msg += f"• {r.get('address')} | {r.get('host-name','?')}\n"
    await u.message.reply_text(msg if res else "Tidak ditemukan", parse_mode='HTML'); pool.disconnect(); return ConversationHandler.END

async def ping_start(u, c): await u.message.reply_text("<b>📡 PING DARI IP:</b>\nKetik source IP:"); return PING_TARGET
async def do_ping_test(u, c):
    ip = u.message.text; pool = connect_mt(); api = pool.get_api()
    try:
        res = api.get_binary_resource('/').call('ping', {'address': '8.8.8.8', 'src-address': ip, 'count': '5'})
        msg = f"<b>🌐 PING DARI {ip}</b>\n"
        for p in res: msg += f"{'✅' if int(p.get('received',1))>0 else '❌'} <code>{p.get('time','timeout')}</code>\n"
        await u.message.reply_text(msg, parse_mode='HTML')
    finally: pool.disconnect(); return ConversationHandler.END

async def gen_start(u, c): await u.callback_query.edit_message_text("<b>⌨️ PREFIX:</b>"); return PREFIX
async def get_prefix(u, c): c.user_data['prefix'] = u.message.text; return PROFILE
async def get_profile(u, c): 
    c.user_data['profile'] = u.callback_query.data.replace('prof_',''); await u.callback_query.edit_message_text("<b>🔢 JUMLAH:</b>"); return QTY
async def finalize_gen(u, c):
    qty, data = int(u.message.text), c.user_data; pool = connect_mt(); api = pool.get_api()
    for _ in range(qty): code = generate_code(data['prefix']); api.get_resource('/ip/hotspot/user').call('add', {'name': code, 'password': code, 'profile': data['profile']})
    await u.message.reply_text("✅ Selesai!"); pool.disconnect(); return ConversationHandler.END

async def manual_start(u, c): await u.callback_query.edit_message_text("<b>👤 USER MANUAL:</b>"); return MAN_USER
async def get_man_user(u, c):
    c.user_data['man_user'] = u.message.text; pool = connect_mt(); api = pool.get_api()
    kb = [[InlineKeyboardButton(p.get('name'), callback_data=f"mprof_{p.get('name')}")] for p in api.get_resource('/ip/hotspot/user/profile').call('print')]
    pool.disconnect(); await u.message.reply_text("<b>📋 PILIH PROFILE:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML'); return MAN_PROF
async def finalize_manual(u, c):
    prof, user_val = u.callback_query.data.replace('mprof_', ''), c.user_data['man_user']; pool = connect_mt()
    pool.get_api().get_resource('/ip/hotspot/user').call('add', {'name': user_val, 'password': user_val, 'profile': prof})
    await u.callback_query.edit_message_text(f"✅ <b>USER {user_val} CREATED!</b>", parse_mode='HTML'); pool.disconnect(); return ConversationHandler.END

# --- RUN BOT ---
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gen_start, pattern='^hs_gen_start$'), 
                      CallbackQueryHandler(manual_start, pattern='^hs_man_start$'),
                      MessageHandler(filters.Regex('^🔍 CARI IP$'), search_ip_start),
                      MessageHandler(filters.Regex('^📡 PING DARI IP$'), ping_start)],
        states={PREFIX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prefix)],
                PROFILE: [CallbackQueryHandler(get_profile, pattern='^prof_')],
                QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_gen)],
                MAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_man_user)],
                MAN_PROF: [CallbackQueryHandler(finalize_manual, pattern='^mprof_')],
                SEARCH_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_search_ip)],
                PING_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_ping_test)]},
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

# --- STREAMLIT THREADING ---
if __name__ == '__main__':
    if "bot_running" not in st.session_state:
        st.session_state.bot_running = True
        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()
        st.info("🟢 Bot Thread Active")
