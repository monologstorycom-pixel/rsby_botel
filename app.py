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
st.title("📡 NOC Bot Server")
st.subheader("PT AURI STEEL METALINDO")

# --- KONFIGURASI SECRETS ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    MT_HOST = st.secrets["MIKROTIK_HOST"]
    MT_USER = st.secrets["MIKROTIK_USER"]
    MT_PASS = st.secrets["MIKROTIK_PASS"]
    MT_PORT = int(st.secrets["MIKROTIK_PORT"])
    st.success("✅ Konfigurasi Secrets Terkoneksi!")
except Exception as e:
    st.error("❌ Secrets Belum Diisi di Dashboard Streamlit!")
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
    user_name = update.effective_user.first_name
    keyboard = [
        ['📝 DHCP Leases', '🔌 Interfaces'], 
        ['🚀 Speedtest WAN', '🛡️ Queues Limit'], 
        ['🔑 Hotspot MGMT', '🔍 CARI IP'], 
        ['📡 PING DARI IP', '⚙️ System Info']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome = (f"<b>🚀 NOC SYSTEM ONLINE v3.0</b>\n"
               f"<b>PT AURI STEEL METALINDO</b>\n"
               f"<code>──────────────────────────────</code>\n"
               f"Halo, <b>{user_name}</b>!\n"
               f"Node: 🖥️ <b>RB450Gx4</b>\n"
               f"Status: 🟢 <b>Semua Fitur Aktif & Aman</b>\n"
               f"<code>──────────────────────────────</code>")
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

# --- LOGIKA MENU UTAMA ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    pool = connect_mt()
    if not pool:
        await update.message.reply_text("❌ <b>MikroTik kaga respon!</b> Cek IP/Firewall di Winbox.", parse_mode='HTML')
        return
    api = pool.get_api()

    if text == '🚀 Speedtest WAN':
        sent_msg = await update.message.reply_text("🚀 <b>Speedtest PPPoE...</b>", parse_mode='HTML')
        wan, rx_s, tx_s = "pppoe-out1", [], []
        for i in range(1, 11):
            try:
                stats = api.get_resource('/interface').call('monitor-traffic', {'interface': wan, 'once': ''})[0]
                rx_s.append(int(stats.get('rx-bits-per-second', 0))/1024/1024)
                tx_s.append(int(stats.get('tx-bits-per-second', 0))/1024/1024)
                await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_msg.message_id, text=f"🚀 <b>Test Jalur... {i*10}%</b>", parse_mode='HTML')
            except: pass
            await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_msg.message_id, text=f"<b>✅ HASIL:</b> DL {max(rx_s):.2f} | UL {max(tx_s):.2f} Mbps", parse_mode='HTML')

    elif text == '📝 DHCP Leases':
        kb = [[InlineKeyboardButton("📡 LAN (1.x)", callback_data="ls_range_192.168.1."), InlineKeyboardButton("📡 WIFI (11.x)", callback_data="ls_range_172.16.11.")],
              [InlineKeyboardButton("📡 CCTV (50.x)", callback_data="ls_range_192.168.50."), InlineKeyboardButton("📡 PUB (10.x)", callback_data="ls_range_10.10.10.")],
              [InlineKeyboardButton("📡 LOG (100.x)", callback_data="ls_range_10.10.100.")]]
        await update.message.reply_text("<b>📝 DHCP LEASES (5 SEGMENT)</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔌 Interfaces':
        ints = api.get_resource('/interface').call('print')
        kb = [[InlineKeyboardButton(f"{'✅' if i.get('disabled')=='false' else '❌'} {i.get('name')}", callback_data=f"intset_{'dis' if i.get('disabled')=='false' else 'en'}_{i.get('name')}")] for i in ints[:10]]
        await update.message.reply_text("<b>🔌 INTERFACE CONTROL</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🔑 Hotspot MGMT':
        kb = [[InlineKeyboardButton("➕ VOUCHER", callback_data="hs_gen_start"), InlineKeyboardButton("👤 MANUAL", callback_data="hs_man_start")], [InlineKeyboardButton("👥 AKTIF", callback_data="hs_active")]]
        await update.message.reply_text("<b>🔑 HOTSPOT MGMT</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif text == '🛡️ Queues Limit':
        queues = api.get_resource('/queue/simple').call('print')
        msg = "<b>🛡️ BANDWIDTH CONTROL</b>\n"
        for q in queues[:10]: msg += f"• {q.get('name')}: {q.get('max-limit')}\n"
        await update.message.reply_text(msg, parse_mode='HTML')

    elif text == '⚙️ System Info':
        res = api.get_resource('/system/resource').call('print')[0]
        await update.message.reply_text(f"CPU: {res.get('cpu-load')}% | Uptime: {res.get('uptime')}", parse_mode='HTML')
    
    pool.disconnect()

# --- CALLBACK HANDLER ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); data = query.data.split('_')
    pool = connect_mt(); api = pool.get_api() if pool else None
    if not api: return

    if data[0] == "ls":
        all_l = api.get_resource('/ip/dhcp-server/lease').call('print')
        fil = [l for l in all_l if l.get('address', '').startswith(data[2])]
        msg = f"<b>📝 LEASES: {data[2]}x</b>\n"
        for l in fil[:10]: msg += f"• {l.get('address')} | {l.get('host-name','?')}\n"
        await query.edit_message_text(msg, parse_mode='HTML')
    elif data[0] == "intset":
        api.get_resource('/interface').call('set', {'numbers': data[2], 'disabled': ('yes' if data[1]=='dis' else 'no')})
        await query.edit_message_text(f"✅ Interface {data[2]} Updated!", parse_mode='HTML')
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
    await u.message.reply_text(msg if res else "Kaga nemu, Bro!", parse_mode='HTML'); pool.disconnect(); return ConversationHandler.END

async def ping_start(u, c): await u.message.reply_text("<b>📡 PING DARI IP:</b>\nSource IP:"); return PING_TARGET
async def do_ping_test(u, c):
    ip = u.message.text; pool = connect_mt(); api = pool.get_api()
    try:
        res = api.get_binary_resource('/').call('ping', {'address': '8.8.8.8', 'src-address': ip, 'count': '5'})
        msg = f"<b>🌐 HASIL PING DARI {ip}:</b>\n"
        for p in res: msg += f"{'✅' if int(p.get('received',1))>0 else '❌'} <code>{p.get('time','timeout')}</code>\n"
        await u.message.reply_text(msg, parse_mode='HTML')
    except: await u.message.reply_text("❌ IP kaga valid atau mati!")
    finally: pool.disconnect(); return ConversationHandler.END

async def gen_start(u, c): await u.callback_query.edit_message_text("<b>⌨️ PREFIX:</b>"); return PREFIX
async def get_prefix(u, c): c.user_data['prefix'] = u.message.text; return PROFILE
async def get_profile(u, c): c.user_data['profile'] = u.callback_query.data.replace('prof_',''); await u.callback_query.edit_message_text("<b>🔢 JUMLAH:</b>"); return QTY
async def finalize_gen(u, c):
    qty, data = int(u.message.text), c.user_data; pool = connect_mt(); api = pool.get_api()
    for _ in range(qty): code = generate_code(data['prefix']); api.get_resource('/ip/hotspot/user').call('add', {'name': code, 'password': code, 'profile': data['profile']})
    await u.message.reply_text("✅ Selesai!"); pool.disconnect(); return ConversationHandler.END

async def manual_start(u, c): await u.callback_query.edit_message_text("<b>👤 USER MANUAL:</b>"); return MAN_USER
async def get_man_user(u, c): c.user_data['man_user'] = u.message.text; return MAN_PROF
async def finalize_manual(u, c):
    prof, u_val = u.callback_query.data.replace('mprof_', ''), c.user_data['man_user']; pool = connect_mt()
    pool.get_api().get_resource('/ip/hotspot/user').call('add', {'name': u_val, 'password': u_val, 'profile': prof})
    await u.callback_query.edit_message_text(f"✅ User {u_val} Created!"); pool.disconnect(); return ConversationHandler.END

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
                QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_gen)],
                MAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_man_user)],
                SEARCH_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_search_ip)],
                PING_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_ping_test)]},
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    if "bot_active" not in st.session_state:
        st.session_state.bot_active = True
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
    st.write("🟢 Server NOC Aktif & Standby!")
