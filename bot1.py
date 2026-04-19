import logging
import json
import os
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- CẤU HÌNH BẢO MẬT ---
# Code sẽ tự động lấy Token từ biến môi trường của hệ thống (Railway/Render)
# Bạn cần thêm biến 'BOT_TOKEN' vào phần Variables của nhà cung cấp hosting.
BOT_TOKEN = os.getenv('BOT_TOKEN')

ADMIN_IDS = [8393067202]
BANK_STK = '144881'
BANK_NAME = 'MBBank'

DATA_FILE = 'players.json'
HISTORY_FILE = 'history.json'
INITIAL_BALANCE = 50000

# Thiết lập nhật ký hoạt động
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- QUẢN LÝ DỮ LIỆU ---
def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc file {file}: {e}")
            return default
    return default

def save_data(file, data):
    try:
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Lỗi lưu file {file}: {e}")

# Khởi tạo dữ liệu
players = load_data(DATA_FILE, {})
game_history = load_data(HISTORY_FILE, [])
user_states = {}

def get_player(user):
    uid = str(user.id)
    if uid not in players:
        players[uid] = {
            "id": user.id, 
            "username": user.username or user.first_name, 
            "balance": INITIAL_BALANCE
        }
        save_data(DATA_FILE, players)
    return players[uid]

# --- LOGIC TRÒ CHƠI ---
ITEMS = ['⚪️', '🔴']
MULTIPLIERS = {
    'Chẵn': 1.95, 
    'Lẻ': 1.95, 
    '4 Trắng (x12)': 12, 
    '4 Đỏ (x12)': 12, 
    '3 Trắng 1 Đỏ (x3.5)': 3.5, 
    '3 Đỏ 1 Trắng (x3.5)': 3.5
}
BET_MAP = {
    'Chẵn': 'chan', 
    'Lẻ': 'le', 
    '4 Trắng (x12)': '4trang', 
    '4 Đỏ (x12)': '4do', 
    '3 Trắng 1 Đỏ (x3.5)': '3trang1do', 
    '3 Đỏ 1 Trắng (x3.5)': '3do1trang'
}

def run_game_logic():
    res = [random.choice(ITEMS) for _ in range(4)]
    reds = res.count('🔴')
    outcome = "chan" if reds % 2 == 0 else "le"
    detail = ""
    if reds == 4: detail = "4do"
    elif reds == 0: detail = "4trang"
    elif reds == 1: detail = "3trang1do"
    elif reds == 3: detail = "3do1trang"
    
    game_history.append({"result": "".join(res), "outcome": outcome})
    if len(game_history) > 100: game_history.pop(0)
    save_data(HISTORY_FILE, game_history)
    return res, outcome, detail

# --- CÁC HÀM XỬ LÝ CHÍNH ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return
    p = get_player(user)
    uid = str(user.id)
    user_states.pop(uid, None)
    
    kb = [
        [KeyboardButton('🎮 Chơi Game'), KeyboardButton('📊 Lịch Sử')],
        [KeyboardButton('💳 Nạp Tiền'), KeyboardButton('🏧 Rút Tiền')],
        [KeyboardButton('📊 Tài Khoản'), KeyboardButton('📜 Hướng Dẫn')]
    ]
    if user.id in ADMIN_IDS: kb.append([KeyboardButton('🛠 Quản Trị')])
    
    await update.message.reply_text(
        f"🎰 **XÓC ĐĨA CASINO** 🎰\n\n👤 Người chơi: **{p['username']}**\n💰 Số dư: `{p['balance']:,}` VNĐ",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    if not user or not text: return
    uid = str(user.id)
    p = get_player(user)

    if text in ['🔙 Quay lại', '🔙 Quay lại Menu']:
        user_states.pop(uid, None)
        return await start(update, context)

    if text == '🎮 Chơi Game':
        kb = [
            [KeyboardButton('Chẵn'), KeyboardButton('Lẻ')], 
            [KeyboardButton('3 Trắng 1 Đỏ (x3.5)'), KeyboardButton('3 Đỏ 1 Trắng (x3.5)')], 
            [KeyboardButton('4 Trắng (x12)'), KeyboardButton('4 Đỏ (x12)')], 
            [KeyboardButton('🔙 Quay lại')]
        ]
        return await update.message.reply_text("🎲 Mời bạn chọn cửa đặt cược:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    if text in MULTIPLIERS:
        user_states[uid] = {'state': 'BET_AMT', 'choice': text}
        return await update.message.reply_text(f"🎯 Bạn đặt vào: **{text}**\n💰 Nhập số tiền muốn cược:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))

    if uid in user_states and user_states[uid]['state'] == 'BET_AMT':
        try:
            amt_str = "".join(filter(str.isdigit, text))
            if not amt_str: return
            amt = int(amt_str)
            choice = user_states[uid]['choice']
            
            if p['balance'] < amt: 
                return await update.message.reply_text("❌ Số dư không đủ!")
            
            p['balance'] -= amt
            save_data(DATA_FILE, players)
            user_states.pop(uid, None)
            
            msg = await update.message.reply_text(f"🎲 Đang xóc đĩa...")
            await asyncio.sleep(1.5)
            
            res, out, det = run_game_logic()
            is_winner = (BET_MAP[choice] == out or BET_MAP[choice] == det)
            
            res_msg = f"Kết quả: [ **{' '.join(res)}** ]\n➜ Thắng: **{out.upper()}**\n\n"
            if is_winner:
                win_amt = int(amt * MULTIPLIERS[choice])
                p['balance'] += win_amt
                res_msg += f"🎉 Thắng: `+{win_amt:,}` VNĐ"
            else:
                res_msg += f"💀 Thua: `-{amt:,}` VNĐ"
            
            save_data(DATA_FILE, players)
            await msg.edit_text(res_msg + f"\n💰 Số dư: `{p['balance']:,}` VNĐ", parse_mode='Markdown')
            return
        except: return

    if text == '💳 Nạp Tiền':
        user_states[uid] = {'state': 'NAP_AMT'}
        return await update.message.reply_text("🏦 Nhập số tiền nạp:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))

    if uid in user_states and user_states[uid]['state'] == 'NAP_AMT':
        try:
            amt = int("".join(filter(str.isdigit, text)))
            url = f"https://img.vietqr.io/image/{BANK_NAME}-{BANK_STK}-compact.jpg?amount={amt}&addInfo=NAP%20{uid}"
            await update.message.reply_photo(url, caption=f"✅ Nạp: `{amt:,}` VNĐ\n📌 Nội dung: `NAP {uid}`", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu')]], resize_keyboard=True))
            for aid in ADMIN_IDS:
                kb = [[InlineKeyboardButton("Duyệt", callback_data=f"ap_{uid}_{amt}")]]
                await context.bot.send_message(aid, f"🔔 NẠP: {user.first_name} | `{amt:,}`", reply_markup=InlineKeyboardMarkup(kb))
            user_states.pop(uid, None)
            return
        except: return

    if text == '🏧 Rút Tiền':
        user_states[uid] = {'state': 'RUT_AMT'}
        return await update.message.reply_text("🏦 Nhập số tiền rút (Min 50k):", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))

    if uid in user_states and user_states[uid]['state'] == 'RUT_AMT':
        try:
            amt = int("".join(filter(str.isdigit, text)))
            if amt < 50000 or p['balance'] < amt: return await update.message.reply_text("❌ Không hợp lệ.")
            user_states[uid] = {'state': 'RUT_INFO', 'amt': amt}
            return await update.message.reply_text("💳 Nhập STK - Tên - Ngân hàng:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))
        except: return

    if uid in user_states and user_states[uid]['state'] == 'RUT_INFO':
        amt = user_states[uid]['amt']
        p['balance'] -= amt
        save_data(DATA_FILE, players)
        await update.message.reply_text("✅ Đã gửi yêu cầu rút.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu')]], resize_keyboard=True))
        for aid in ADMIN_IDS:
            kb = [[InlineKeyboardButton("Duyệt", callback_data=f"wd_ok_{uid}_{amt}"), InlineKeyboardButton("Từ chối", callback_data=f"wd_no_{uid}_{amt}")]]
            await context.bot.send_message(aid, f"⚠️ RÚT: {user.first_name} | `{amt:,}`\n🏦: {text}", reply_markup=InlineKeyboardMarkup(kb))
        user_states.pop(uid, None)
        return

    if text == '📊 Lịch Sử':
        if not game_history: return await update.message.reply_text("Trống.")
        icons = ["🔴" if h['outcome'] == 'chan' else "⚪️" for h in game_history[-20:]]
        await update.message.reply_text(f"📊 Lịch sử:\n{' '.join(icons)}")

    if text == '📊 Tài Khoản':
        await update.message.reply_text(f"👤: {p['username']}\n🆔: `{uid}`\n💰: `{p['balance']:,}` VNĐ", parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    action = data[0]
    
    if action == "ap":
        tid, amt = data[1], int(data[2])
        if tid in players:
            players[tid]['balance'] += amt
            save_data(DATA_FILE, players)
            await query.edit_message_text(f"✅ Đã duyệt nạp {amt:,} cho {tid}")
            try: await context.bot.send_message(tid, f"💰 Tài khoản đã được cộng +{amt:,} VNĐ")
            except: pass
    elif action == "wd":
        sub = data[1]
        tid, amt = data[2], int(data[3])
        if sub == "ok":
            await query.edit_message_text(f"✅ Đã duyệt rút {amt:,} cho {tid}")
            try: await context.bot.send_message(tid, f"🏧 Rút tiền thành công: {amt:,} VNĐ")
            except: pass
        else:
            if tid in players:
                players[tid]['balance'] += amt
                save_data(DATA_FILE, players)
                await query.edit_message_text(f"❌ Đã từ chối rút cho {tid}. Hoàn tiền xong.")
                try: await context.bot.send_message(tid, f"⚠️ Admin từ chối rút {amt:,}. Tiền đã hoàn lại.")
                except: pass

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("LỖI: Chưa có BOT_TOKEN trong biến môi trường!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
        print("Bot 24/24 đang chạy...")
        app.run_polling()
