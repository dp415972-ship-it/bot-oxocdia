import logging
import json
import os
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- CẤU HÌNH ---
BOT_TOKEN = os.getenv('BOT_TOKEN', '8747823218:AAE5clUs5rSf-bF_MTQkxlnFiWk3LUUS8AY')
ADMIN_IDS = [8393067202] # Chắc chắn là có dấu ngoặc vuông []
BANK_STK = '144881'
BANK_NAME = 'MBBank'

DATA_FILE = 'players.json'
HISTORY_FILE = 'history.json'
INITIAL_BALANCE = 50000

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- QUẢN LÝ DỮ LIỆU ---
def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return default
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

players = load_data(DATA_FILE, {})
game_history = load_data(HISTORY_FILE, [])
user_states = {}

def get_player(user):
    uid = str(user.id)
    if uid not in players:
        players[uid] = {"id": user.id, "username": user.username or user.first_name, "balance": INITIAL_BALANCE}
        save_data(DATA_FILE, players)
    return players[uid]

# --- LOGIC GAME ---
ITEMS = ['⚪️', '🔴']
MULTIPLIERS = {'Chẵn': 1.95, 'Lẻ': 1.95, '4 Trắng (x12)': 12, '4 Đỏ (x12)': 12, '3 Trắng 1 Đỏ (x3.5)': 3.5, '3 Đỏ 1 Trắng (x3.5)': 3.5}
BET_MAP = {'Chẵn': 'chan', 'Lẻ': 'le', '4 Trắng (x12)': '4trang', '4 Đỏ (x12)': '4do', '3 Trắng 1 Đỏ (x3.5)': '3trang1do', '3 Đỏ 1 Trắng (x3.5)': '3do1trang'}

def run_logic():
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

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user)
    uid = str(user.id)
    user_states.pop(uid, None)
    
    kb = [
        [KeyboardButton('🎮 Chơi Game'), KeyboardButton('📊 Lịch Sử')],
        [KeyboardButton('💳 Nạp Tiền'), KeyboardButton('🏧 Rút Tiền')],
        [KeyboardButton('📊 Tài Khoản'), KeyboardButton('📜 Hướng Dẫn')]
    ]
    # Kiểm tra Admin để hiện nút
    if user.id in ADMIN_IDS:
        kb.append([KeyboardButton('🛠 Quản Trị')])
    
    await update.message.reply_text(
        f"🎰 **XÓC ĐĨA PRO** 🎰\n👤: {p['username']}\n💰: `{p['balance']:,}` VNĐ",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    uid = str(user.id)
    p = get_player(user)

    if text in ['🔙 Quay lại', '🔙 Quay lại Menu']:
        user_states.pop(uid, None)
        return await start(update, context)

    # --- XỬ LÝ NÚT QUẢN TRỊ ---
    if text == '🛠 Quản Trị':
        if user.id not in ADMIN_IDS:
            return await update.message.reply_text("❌ Bạn không có quyền Admin.")
        
        total_users = len(players)
        total_balance = sum(u['balance'] for u in players.values())
        
        # Tạo Menu Admin bằng nút bấm Inline
        keyboard = [
            [InlineKeyboardButton("👥 Danh Sách Người Chơi", callback_data="admin_list")],
            [InlineKeyboardButton("💰 Cộng/Trừ Tiền", callback_data="admin_setbal")],
            [InlineKeyboardButton("📊 Làm Mới Thống Kê", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = (
            "🛠 **HỆ THỐNG QUẢN TRỊ**\n\n"
            f"👥 Tổng người chơi: `{total_users}`\n"
            f"💵 Tổng số dư khách: `{total_balance:,}` VNĐ\n\n"
            "Chọn một chức năng bên dưới để điều hành:"
        )
        return await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

    # Chơi Game
    if text == '🎮 Chơi Game':
        kb = [[KeyboardButton('Chẵn'), KeyboardButton('Lẻ')], [KeyboardButton('3 Trắng 1 Đỏ (x3.5)'), KeyboardButton('3 Đỏ 1 Trắng (x3.5)')], [KeyboardButton('4 Trắng (x12)'), KeyboardButton('4 Đỏ (x12)')], [KeyboardButton('🔙 Quay lại')]]
        return await update.message.reply_text("🎲 Chọn cửa đặt:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    if text in MULTIPLIERS:
        user_states[uid] = {'state': 'BET_AMT', 'choice': text}
        return await update.message.reply_text(f"🎯 Cửa: {text}\n💰 Nhập tiền cược:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))

    if uid in user_states and user_states[uid]['state'] == 'BET_AMT':
        try:
            amt = int("".join(filter(str.isdigit, text)))
            choice = user_states[uid]['choice']
            if p['balance'] < amt: return await update.message.reply_text("❌ Không đủ tiền!")
            
            p['balance'] -= amt
            save_data(DATA_FILE, players)
            user_states.pop(uid, None)
            
            msg = await update.message.reply_text(f"🎲 Đang xóc...")
            await asyncio.sleep(1.5)
            
            res, out, det = run_logic()
            win = (BET_MAP[choice] == out or BET_MAP[choice] == det)
            
            res_msg = f"Kết quả: [ {' '.join(res)} ]\n➜ **{out.upper()}**\n"
            if win:
                win_amt = int(amt * MULTIPLIERS[choice])
                p['balance'] += win_amt
                res_msg += f"🎉 THẮNG: `+{win_amt:,}`"
            else: res_msg += f"💀 THUA: `-{amt:,}`"
            
            save_data(DATA_FILE, players)
            await msg.edit_text(res_msg + f"\n💰 Dư: `{p['balance']:,}`", parse_mode='Markdown')
            return
        except: return

    # Nạp/Rút
    if text == '💳 Nạp Tiền':
        user_states[uid] = {'state': 'NAP'}
        return await update.message.reply_text("🏦 Nhập số tiền nạp:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))

    if uid in user_states and user_states[uid]['state'] == 'NAP':
        try:
            amt = int("".join(filter(str.isdigit, text)))
            url = f"https://img.vietqr.io/image/{BANK_NAME}-{BANK_STK}-compact.jpg?amount={amt}&addInfo=NAP%20{uid}"
            await update.message.reply_photo(url, caption=f"✅ Lệnh nạp: `{amt:,}`\nNội dung: `NAP {uid}`", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu')]], resize_keyboard=True))
            for aid in ADMIN_IDS:
                kb = [[InlineKeyboardButton("✅ Duyệt", callback_data=f"ap_{uid}_{amt}")]]
                await context.bot.send_message(aid, f"🔔 NẠP: {user.first_name} | ID: `{uid}` | `{amt:,}`", reply_markup=InlineKeyboardMarkup(kb))
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
            return await update.message.reply_text("💳 Nhập STK - Bank - Tên:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))
        except: return

    if uid in user_states and user_states[uid]['state'] == 'RUT_INFO':
        amt = user_states[uid]['amt']
        p['balance'] -= amt
        save_data(DATA_FILE, players)
        await update.message.reply_text("✅ Đã gửi yêu cầu rút.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu')]], resize_keyboard=True))
        for aid in ADMIN_IDS:
            kb = [[InlineKeyboardButton("✅ Duyệt", callback_data=f"wd_ok_{uid}_{amt}"), InlineKeyboardButton("❌ Từ chối", callback_data=f"wd_no_{uid}_{amt}")]]
            await context.bot.send_message(aid, f"⚠️ RÚT: {user.first_name}\n💰: `{amt:,}`\n🏦: {text}", reply_markup=InlineKeyboardMarkup(kb))
        user_states.pop(uid, None)
        return

    if text == '📊 Lịch Sử':
        if not game_history: return await update.message.reply_text("Chưa có dữ liệu.")
        icons = ["🔴" if h['outcome'] == 'chan' else "⚪️" for h in game_history[-20:]]
        await update.message.reply_text(f"Lịch sử:\n{' '.join(icons)}")

    if text == '📊 Tài Khoản':
        await update.message.reply_text(f"👤: {p['username']}\n🆔: `{uid}`\n💰: `{p['balance']:,}` VNĐ", parse_mode='Markdown')

# --- LỆNH ADMIN (GÕ TAY) ---
async def set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        tid, amt = context.args[0], int(context.args[1])
        if tid in players:
            players[tid]['balance'] = amt
            save_data(DATA_FILE, players)
            await update.message.reply_text(f"✅ Đã đặt số dư ID {tid} thành {amt:,}")
        else: await update.message.reply_text("❌ ID không tồn tại.")
    except: await update.message.reply_text("HD: `/setbal ID SoTien`")

async def cb_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    action = data[0]
    
    # Xử lý các chức năng Admin mới
    if action == "admin":
        sub = data[1]
        if sub == "stats":
            total_users = len(players)
            total_balance = sum(u['balance'] for u in players.values())
            await query.answer("Đã làm mới thống kê!")
            await query.edit_message_text(
                f"🛠 **HỆ THỐNG QUẢN TRỊ** (Updated)\n\n👥 Tổng người chơi: `{total_users}`\n💵 Tổng số dư khách: `{total_balance:,}` VNĐ",
                reply_markup=query.message.reply_markup, parse_mode='Markdown'
            )
        elif sub == "list":
            user_list = "\n".join([f"• {u['username']} (ID: `{uid}`): `{u['balance']:,}`" for uid, u in list(players.items())[:10]])
            await query.message.reply_text(f"👥 **DANH SÁCH 10 NGƯỜI CHƠI MỚI:**\n\n{user_list}", parse_mode='Markdown')
            await query.answer()
        elif sub == "setbal":
            await query.message.reply_text("Để cộng tiền, hãy dùng lệnh gõ tay:\n`/setbal [ID] [Số_tiền]`")
            await query.answer()
        return

    # Duyệt nạp/rút tiền
    if action == "ap":
        tid, amt = data[1], int(data[2])
        players[tid]['balance'] += amt
        save_data(DATA_FILE, players)
        await query.edit_message_text(f"✅ Đã duyệt nạp {amt:,} cho {tid}")
        try: await context.bot.send_message(tid, f"💰 Đã cộng +{amt:,} VNĐ")
        except: pass
    elif action == "wd":
        sub = data[1]
        target_id, real_amt = data[2], int(data[3])
        if sub == "ok":
            await query.edit_message_text(f"✅ Đã duyệt rút {real_amt:,} cho {target_id}")
            try: await context.bot.send_message(target_id, f"🏧 Rút tiền thành công: {real_amt:,} VNĐ")
            except: pass
        else:
            players[target_id]['balance'] += real_amt
            save_data(DATA_FILE, players)
            await query.edit_message_text(f"❌ Từ chối rút. Đã hoàn tiền.")
            try: await context.bot.send_message(target_id, f"⚠️ Admin từ chối rút. Tiền đã hoàn lại.")
            except: pass

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setbal', set_balance)) 
    app.add_handler(CallbackQueryHandler(cb_query))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    app.run_polling()
