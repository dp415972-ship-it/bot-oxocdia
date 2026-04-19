import logging
import json
import os
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# CẤU HÌNH BOT
# ==========================================
BOT_TOKEN = '8747823218:AAE5clUs5rSf-bF_MTQkxlnFiWk3LUUS8AY'
ADMIN_IDS = [8393067202]  # ID Admin của bạn
BANK_STK = '144881'       # Số tài khoản nhận tiền
BANK_NAME = 'MBBank'      # Tên ngân hàng

DATA_FILE = 'players.json'
HISTORY_FILE = 'history.json'
INITIAL_BALANCE = 50000
ADMIN_TELEGRAM_LINK = "http://t.me/jobd01"

# Thiết lập logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

user_states = {}

# --- Quản lý dữ liệu ---
def load_data(file, default):
    try:
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Lỗi khi đọc file {file}: {e}")
    return default

def save_data(file, data):
    try:
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Lỗi khi lưu file {file}: {e}")

players = load_data(DATA_FILE, {})
game_history = load_data(HISTORY_FILE, [])

def get_player(user):
    user_id = str(user.id)
    if user_id not in players:
        players[user_id] = {
            "id": user.id,
            "username": user.username or user.first_name,
            "balance": INITIAL_BALANCE,
            "total_bet": 0,
            "total_win": 0
        }
        save_data(DATA_FILE, players)
    return players[user_id]

# --- Logic Game ---
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

def xoc_dia_logic():
    result = [random.choice(ITEMS) for _ in range(4)]
    red_count = result.count('🔴')
    white_count = result.count('⚪️')
    
    outcome = "chan" if red_count % 2 == 0 else "le"
    detail = ""
    
    if red_count == 4: detail = "4do"
    elif white_count == 4: detail = "4trang"
    elif red_count == 3: detail = "3do1trang"
    elif white_count == 3: detail = "3trang1do"
    
    game_history.append({"result": "".join(result), "outcome": outcome})
    if len(game_history) > 100: game_history.pop(0)
    save_data(HISTORY_FILE, game_history)
    
    return result, outcome, detail

# --- Menu ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return
    player = get_player(user)
    user_id = str(user.id)
    if user_id in user_states: del user_states[user_id]
    
    keyboard = [
        [KeyboardButton('🎮 Chơi Game'), KeyboardButton('📊 Lịch Sử Cầu')],
        [KeyboardButton('💳 Nạp Tiền'), KeyboardButton('🏧 Rút Tiền')],
        [KeyboardButton('📊 Tài Khoản'), KeyboardButton('📜 Hướng Dẫn')]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([KeyboardButton('🛠 Quản Trị Hệ Thống')])
        
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"🎰 **XÓC ĐĨA CASINO PRO** 🎰\n\n"
        f"👤 Chào mừng: **{player['username']}**\n"
        f"💰 Số dư: `{player['balance']:,}` VNĐ",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    keyboard = [
        [KeyboardButton('👥 Danh sách người chơi'), KeyboardButton('📈 Thống kê chung')],
        [KeyboardButton('🔙 Quay lại Menu Chính')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🛠 **DASHBOARD QUẢN TRỊ VIÊN**", reply_markup=reply_markup, parse_mode='Markdown')

# --- Xử lý Callback Query ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = str(user.id)
    data = query.data.split("_")
    action = data[0]
    
    if action == "approve":
        if user.id not in ADMIN_IDS: return
        target_id, amount = data[1], int(data[2])
        if target_id in players:
            players[target_id]['balance'] += amount
            save_data(DATA_FILE, players)
            await query.answer("✅ Đã duyệt nạp tiền!")
            await query.edit_message_text(f"✅ **ĐÃ DUYỆT NẠP**\n👤 ID: `{target_id}`\n💰 Số tiền: `+{amount:,}` VNĐ", parse_mode='Markdown')
            try:
                await context.bot.send_message(chat_id=int(target_id), text=f"💰 **THÔNG BÁO NẠP TIỀN**\nAdmin đã duyệt nạp: `+{amount:,}` VNĐ\nSố dư: `{players[target_id]['balance']:,}` VNĐ", parse_mode='Markdown')
            except: pass

    elif action == "wd":
        if user.id not in ADMIN_IDS: return
        sub_action, target_id, amount = data[1], data[2], int(data[3])
        if sub_action == "confirm":
            await query.answer("✅ Đã xác nhận rút!")
            await query.edit_message_text(f"✅ **ĐÃ DUYỆT RÚT**\n👤 ID: `{target_id}`\n💰 Số tiền: `-{amount:,}` VNĐ", parse_mode='Markdown')
            try:
                await context.bot.send_message(chat_id=int(target_id), text=f"🏧 **RÚT TIỀN THÀNH CÔNG**\nSố tiền: `{amount:,}` VNĐ đã được chuyển.", parse_mode='Markdown')
            except: pass
        elif sub_action == "reject":
            if target_id in players:
                players[target_id]['balance'] += amount
                save_data(DATA_FILE, players)
                await query.answer("❌ Đã từ chối rút!")
                await query.edit_message_text(f"❌ **ĐÃ TỪ CHỐI RÚT**\nID: `{target_id}`\nHoàn lại: `{amount:,}` VNĐ", parse_mode='Markdown')

    elif action == "bet":
        choice = data[1]
        user_states[user_id] = {'state': 'BET_AMT', 'choice': choice}
        await query.answer()
        await context.bot.send_message(chat_id=user.id, text=f"🎯 Bạn chọn cược: **{choice}**\n💰 Nhập số tiền muốn đặt cược:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True), parse_mode='Markdown')

# --- Xử lý tin nhắn ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    if not user or not text: return
    user_id = str(user.id)
    player = get_player(user)

    if text in ['🔙 Quay lại Menu Chính', '🔙 Quay lại']: 
        if user_id in user_states: del user_states[user_id]
        return await start(update, context)
        
    if text == '🛠 Quản Trị Hệ Thống': return await admin_panel(update, context)
    if text == '📊 Tài Khoản':
        return await update.message.reply_text(f"👤 Tên: {player['username']}\n🆔 ID: `{player['id']}`\n💰 Dư: `{player['balance']:,}` VNĐ", parse_mode='Markdown')
    if text == '📜 Hướng Dẫn':
        return await update.message.reply_text("📖 **HƯỚNG DẪN**\n\n- Chẵn/Lẻ: x1.95\n- 3 trắng/đỏ: x3.5\n- 4 trắng/đỏ: x12\n- Nạp tối thiểu: 10k\n- Rút tối thiểu: 50k", parse_mode='Markdown')
    if text == '📊 Lịch Sử Cầu':
        if not game_history: return await update.message.reply_text("Chưa có dữ liệu.")
        icons = ["🔴" if h['outcome'] == 'chan' else "⚪️" for h in game_history[-20:]]
        return await update.message.reply_text(f"Lịch sử 20 ván:\n\n{' '.join(icons)}")

    # 1. NẠP TIỀN
    if text == '💳 Nạp Tiền':
        user_states[user_id] = {'state': 'WAITING_DEPOSIT'}
        await update.message.reply_text("🏦 Nhập số tiền bạn muốn nạp:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))
        return

    if user_id in user_states and user_states[user_id].get('state') == 'WAITING_DEPOSIT':
        try:
            amount_str = "".join(filter(str.isdigit, text))
            if not amount_str: raise ValueError
            amount = int(amount_str)
            qr_url = f"https://img.vietqr.io/image/{BANK_NAME}-{BANK_STK}-compact2.jpg?amount={amount}&addInfo=NAP%20{user_id}"
            await update.message.reply_photo(photo=qr_url, caption=f"✅ **LỆNH NẠP {amount:,} VNĐ**\nNội dung ck: `NAP {user_id}`", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu Chính')]], resize_keyboard=True))
            kb = [[InlineKeyboardButton("✅ Duyệt Nạp", callback_data=f"approve_{user_id}_{amount}")]]
            for aid in ADMIN_IDS:
                await context.bot.send_message(chat_id=aid, text=f"🔔 **NẠP MỚI**\n👤 {user.first_name}\n🆔 `{user_id}`\n💰 `{amount:,}` VNĐ", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
            del user_states[user_id]
            return
        except:
            return await update.message.reply_text("❌ Vui lòng nhập số tiền hợp lệ.")

    # 2. RÚT TIỀN
    if text == '🏧 Rút Tiền':
        user_states[user_id] = {'state': 'WITHDRAW_AMT'}
        await update.message.reply_text("🏦 Nhập số tiền muốn rút (Tối thiểu 50,000):", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))
        return

    if user_id in user_states and user_states[user_id].get('state') == 'WITHDRAW_AMT':
        try:
            amount_str = "".join(filter(str.isdigit, text))
            if not amount_str: raise ValueError
            amount = int(amount_str)
            if amount < 50000: return await update.message.reply_text("❌ Tối thiểu 50k.")
            if player['balance'] < amount:
                del user_states[user_id]
                return await update.message.reply_text("❌ Không đủ tiền!", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu Chính')]], resize_keyboard=True))
            user_states[user_id] = {'state': 'WITHDRAW_INFO', 'amount': amount}
            await update.message.reply_text(f"💳 Nhập Thông Tin Nhận Tiền (STK - Ngân Hàng - Tên):", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))
            return
        except:
            return await update.message.reply_text("❌ Vui lòng nhập số tiền hợp lệ.")

    if user_id in user_states and user_states[user_id].get('state') == 'WITHDRAW_INFO':
        amount = user_states[user_id]['amount']
        player['balance'] -= amount
        save_data(DATA_FILE, players)
        await update.message.reply_text("✅ Đã gửi yêu cầu rút tiền.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu Chính')]], resize_keyboard=True))
        kb = [[InlineKeyboardButton("✅ Duyệt Rút", callback_data=f"wd_confirm_{user_id}_{amount}"), InlineKeyboardButton("❌ Từ Chối", callback_data=f"wd_reject_{user_id}_{amount}")]]
        for aid in ADMIN_IDS:
            await context.bot.send_message(chat_id=aid, text=f"⚠️ **YÊU CẦU RÚT**\n👤 {user.first_name}\n💰 `{amount:,}` VNĐ\n🏦 `{text}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        del user_states[user_id]
        return

    # 3. CHƠI GAME
    if text == '🎮 Chơi Game':
        keyboard = [
            [KeyboardButton('Chẵn'), KeyboardButton('Lẻ')],
            [KeyboardButton('3 Trắng 1 Đỏ (x3.5)'), KeyboardButton('3 Đỏ 1 Trắng (x3.5)')],
            [KeyboardButton('4 Trắng (x12)'), KeyboardButton('4 Đỏ (x12)')],
            [KeyboardButton('🔙 Quay lại')]
        ]
        await update.message.reply_text("🎲 Chọn cửa đặt cược:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if text in MULTIPLIERS:
        user_states[user_id] = {'state': 'BET_AMT', 'choice': text}
        await update.message.reply_text(f"🎯 Đặt: {text}\n💰 Nhập tiền cược:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại')]], resize_keyboard=True))
        return

    if user_id in user_states and user_states[user_id].get('state') == 'BET_AMT':
        try:
            amount_str = "".join(filter(str.isdigit, text))
            if not amount_str: raise ValueError
            amount = int(amount_str)
            choice = user_states[user_id]['choice']
            if player['balance'] < amount:
                del user_states[user_id]
                return await update.message.reply_text("❌ Không đủ tiền!", reply_markup=ReplyKeyboardMarkup([[KeyboardButton('🔙 Quay lại Menu Chính')]], resize_keyboard=True))
            
            player['balance'] -= amount
            save_data(DATA_FILE, players)
            del user_states[user_id]
            
            msg = await update.message.reply_text(f"🎲 Đang xóc... `{amount:,}` VNĐ vào {choice}")
            await asyncio.sleep(1)
            
            result, outcome, detail = xoc_dia_logic()
            is_win = (BET_MAP[choice] == outcome or BET_MAP[choice] == detail)
            res_str = " ".join(result)
            
            res_text = f"Kết quả: [ {res_str} ]\n➜ **{outcome.upper()}**\n\n"
            if is_win:
                win_amt = int(amount * MULTIPLIERS[choice])
                player['balance'] += win_amt
                res_text += f"🎉 THẮNG: **+{win_amt:,}** VNĐ"
            else: res_text += f"💀 THUA: **-{amount:,}** VNĐ"
            res_text += f"\n💰 Số dư: `{player['balance']:,}` VNĐ"
            
            save_data(DATA_FILE, players)
            kb = [[InlineKeyboardButton("Chẵn", callback_data="bet_Chẵn"), InlineKeyboardButton("Lẻ", callback_data="bet_Lẻ")]]
            await msg.edit_text(res_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            return
        except:
            return await update.message.reply_text("❌ Vui lòng nhập số tiền cược hợp lệ.")

    # ADMIN PANEL
    if user.id in ADMIN_IDS:
        if text == '👥 Danh sách người chơi':
            msg = "👥 **DANH SÁCH KHÁCH**\n\n"
            for pid, p in list(players.items())[-15:]:
                msg += f"• {p['username']} (`{pid}`): `{p['balance']:,}`\n"
            await update.message.reply_text(msg, parse_mode='Markdown')
        elif text == '📈 Thống kê chung':
            total = sum(p['balance'] for p in players.values())
            await update.message.reply_text(f"📊 **THỐNG KÊ**\n👥 Khách: {len(players)}\n💵 Tổng dư: `{total:,}` VNĐ", parse_mode='Markdown')

async def set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        tid, amt = context.args[0], int(context.args[1])
        if tid in players:
            players[tid]['balance'] = amt
            save_data(DATA_FILE, players)
            await update.message.reply_text(f"✅ Sét ID {tid} = {amt:,}")
    except: pass

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setbal', set_balance))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot đang chạy...")
    app.run_polling()