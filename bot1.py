import logging
import json
import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- CẤU HÌNH ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [8393067202] # ID Telegram của bạn
ADMIN_USERNAME = "@admin_casino" # Username admin để liên hệ
BANK_STK = '144881'
BANK_NAME = 'MBBank'

DATA_FILE = 'players.json'
INITIAL_BALANCE = 10000  # Chơi thử 10k
MIN_WITHDRAW = 100000    # Min rút 100k
REF_COMMISSION = 0.10    # Hoa hồng 10%

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- QUẢN LÝ DỮ LIỆU ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

players = load_data()

def get_player(user, ref_id=None):
    uid = str(user.id)
    if uid not in players:
        players[uid] = {
            "username": user.username or user.first_name, 
            "balance": INITIAL_BALANCE,
            "ref_by": ref_id if (ref_id and ref_id != uid and ref_id in players) else None,
            "total_ref_bonus": 0,
            "play_history": []
        }
        save_data(players)
    return players[uid]

# --- LOGIC GAMES ---

def run_xoc_dia():
    res = [random.choice(['⚪️', '🔴']) for _ in range(4)]
    reds = res.count('🔴')
    outcome = "chan" if reds % 2 == 0 else "le"
    detail = {4: "4do", 0: "4trang", 3: "3do", 1: "3trang"}.get(reds)
    return res, outcome, detail

def run_tai_xiu():
    dices = [random.randint(1, 6) for _ in range(3)]
    total = sum(dices)
    if dices[0] == dices[1] == dices[2]: outcome = "triple"
    else: outcome = "tai" if 11 <= total <= 17 else "xiu"
    return dices, total, outcome

def run_baccarat():
    p_cards = [random.randint(0, 9), random.randint(0, 9)]
    b_cards = [random.randint(0, 9), random.randint(0, 9)]
    p_s, b_s = sum(p_cards) % 10, sum(b_cards) % 10
    out = "player" if p_s > b_s else ("banker" if b_s > p_s else "tie")
    return p_s, b_s, out

# --- KEYBOARDS ---

def menu_main_kb(user_id):
    kb = [
        [InlineKeyboardButton("🎮 SẢNH GAME", callback_data="lobby")],
        [InlineKeyboardButton("💳 NẠP TIỀN", callback_data="dep_list"), InlineKeyboardButton("🏧 RÚT TIỀN", callback_data="withdraw")],
        [InlineKeyboardButton("👥 MỜI BẠN BÈ", callback_data="referral"), InlineKeyboardButton("👤 TÀI KHOẢN", callback_data="account")],
        [InlineKeyboardButton("☎️ LIÊN HỆ ADMIN", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")]
    ]
    return InlineKeyboardMarkup(kb)

def lobby_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 XÓC ĐĨA (Full Vị)", callback_data="game_xd"), InlineKeyboardButton("🔥 TÀI XỈU (Sicbo)", callback_data="game_tx")],
        [InlineKeyboardButton("🃏 BACCARAT", callback_data="game_bc")],
        [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="main")]
    ])

def game_xd_kb(amt=10000):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💰 Cược: {amt:,} (Đổi)", callback_data="setamt_xd")],
        [InlineKeyboardButton("CHẴN x1.95", callback_data=f"bet_xd_chan_{amt}"), InlineKeyboardButton("LẺ x1.95", callback_data=f"bet_xd_le_{amt}")],
        [InlineKeyboardButton("3 TRẮNG x3.5", callback_data=f"bet_xd_3trang_{amt}"), InlineKeyboardButton("3 ĐỎ x3.5", callback_data=f"bet_xd_3do_{amt}")],
        [InlineKeyboardButton("4 TRẮNG x12", callback_data=f"bet_xd_4trang_{amt}"), InlineKeyboardButton("4 ĐỎ x12", callback_data=f"bet_xd_4do_{amt}")],
        [InlineKeyboardButton("🔙 SẢNH", callback_data="lobby")]
    ])

def game_tx_kb(amt=10000):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💰 Cược: {amt:,} (Đổi)", callback_data="setamt_tx")],
        [InlineKeyboardButton("TÀI x1.95", callback_data=f"bet_tx_tai_{amt}"), InlineKeyboardButton("XỈU x1.95", callback_data=f"bet_tx_xiu_{amt}")],
        [InlineKeyboardButton("BÃO (Triple x30)", callback_data=f"bet_tx_triple_{amt}")],
        [InlineKeyboardButton("🔙 SẢNH", callback_data="lobby")]
    ])

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Xử lý link mời: /start ref_12345
    ref_id = None
    if context.args and context.args[0].startswith("ref_"):
        ref_id = context.args[0].replace("ref_", "")
    
    p = get_player(user, ref_id)
    text = (f"💎 **CASINO PRO CLUB** 💎\n\n"
            f"👤 Khách hàng: **{p['username']}**\n"
            f"💰 Số dư: `{p['balance']:,}` VNĐ\n"
            f"🎁 Vốn trải nghiệm: `10,000` VNĐ\n\n"
            f"Hệ thống Casino uy tín, nạp rút tự động 24/7.")
    
    if update.message:
        await update.message.reply_text(text, reply_markup=menu_main_kb(user.id), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=menu_main_kb(user.id), parse_mode='Markdown')

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = update.effective_user
    uid = str(user.id)
    p = get_player(user)
    await query.answer()

    if data == "main": await start(update, context)
    elif data == "lobby": await query.edit_message_text("🎮 **SẢNH TRÒ CHƠI CHUYÊN NGHIỆP**", reply_markup=lobby_kb(), parse_mode='Markdown')
    
    # --- REFERRAL ---
    elif data == "referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
        msg = (f"👥 **CHƯƠNG TRÌNH CTV & ĐẠI LÝ**\n\n"
               f"🎁 Nhận ngay **10%** hoa hồng khi người bạn mời nạp tiền!\n\n"
               f"🔗 Link mời của bạn:\n`{ref_link}`\n\n"
               f"💰 Tổng hoa hồng đã nhận: `{p.get('total_ref_bonus', 0):,}` VNĐ")
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 QUAY LẠI", callback_data="main")]]), parse_mode='Markdown')

    # --- RÚT TIỀN ---
    elif data == "withdraw":
        if p['balance'] < MIN_WITHDRAW:
            await query.message.reply_text(f"❌ Số dư không đủ! Min rút là `{MIN_WITHDRAW:,}` VNĐ.")
        else:
            await query.message.reply_text(f"🏧 Để rút tiền, vui lòng soạn tin nhắn:\n`RUT [Số tiền] [STK] [Ngân hàng]`\nVí dụ: `RUT 150000 12345678 MB`")

    # --- ĐẶT CƯỢC XÓC ĐĨA ---
    elif data.startswith("bet_xd_"):
        parts = data.split("_")
        choice, amt = parts[2], int(parts[3])
        if p['balance'] < amt: return await query.message.reply_text("❌ Số dư không đủ!")
        p['balance'] -= amt
        res, out, det = run_xoc_dia()
        win, mult = False, 0
        if choice in ['chan', 'le']:
            if choice == out: win, mult = True, 1.95
        else:
            if choice == det: win, mult = True, (3.5 if "3" in choice else 12)
        
        if win: p['balance'] += int(amt * mult)
        save_data(players)
        msg = f"🎲 Kết quả: `{' '.join(res)}` ➜ **{out.upper()}**\n"
        msg += f"{'🎉 THẮNG: +'+f'{int(amt*mult):,}' if win else '💀 THUA: -'+f'{amt:,}'}\n💰 Số dư: `{p['balance']:,}`"
        await query.edit_message_text(msg, reply_markup=game_xd_kb(amt), parse_mode='Markdown')

    # --- ĐẶT CƯỢC TÀI XỈU ---
    elif data.startswith("bet_tx_"):
        parts = data.split("_")
        choice, amt = parts[2], int(parts[3])
        if p['balance'] < amt: return await query.message.reply_text("❌ Số dư không đủ!")
        p['balance'] -= amt
        dices, total, out = run_tai_xiu()
        win = (choice == out)
        mult = 30 if choice == "triple" else 1.95
        if win: p['balance'] += int(amt * mult)
        save_data(players)
        msg = f"🔥 Kết quả: `{' + '.join(map(str, dices))} = {total}`\n"
        msg += f"{'🎉 THẮNG: +'+f'{int(amt*mult):,}' if win else '💀 THUA: -'+f'{amt:,}'}\n💰 Số dư: `{p['balance']:,}`"
        await query.edit_message_text(msg, reply_markup=game_tx_kb(amt), parse_mode='Markdown')

    # --- NẠP TIỀN & DUYỆT (ADMIN CHỈ CẦN DUYỆT LÀ NGƯỜI MỜI CÓ TIỀN) ---
    elif data == "dep_list":
        kb = [[InlineKeyboardButton(f"{v}k", callback_data=f"gen_qr_{v}000")] for v in [50, 100, 200, 500]]
        kb.append([InlineKeyboardButton("🔙 QUAY LẠI", callback_data="main")])
        await query.edit_message_text("💳 Chọn mệnh giá nạp:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("gen_qr_"):
        amt = int(data.split("_")[2])
        qr = f"https://img.vietqr.io/image/{BANK_NAME}-{BANK_STK}-compact.jpg?amount={amt}&addInfo=NAP%20{uid}"
        await query.message.reply_photo(qr, caption=f"💰 Mệnh giá: `{amt:,}`\n📌 Nội dung: `NAP {uid}`")
        for aid in ADMIN_IDS:
            await context.bot.send_message(aid, f"🔔 YÊU CẦU NẠP: {p['username']} ({uid})\nSố tiền: `{amt:,}`", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("DUYỆT ✅", callback_data=f"admin_approve_{uid}_{amt}")]]))

    elif data.startswith("admin_approve_"):
        _, _, target_id, amount = data.split("_")
        amount = int(amount)
        if str(user.id) in map(str, ADMIN_IDS):
            target_p = players.get(target_id)
            if target_p:
                target_p['balance'] += amount
                # Tính hoa hồng cho người mời
                if target_p.get('ref_by'):
                    referrer = players.get(target_p['ref_by'])
                    if referrer:
                        commission = int(amount * REF_COMMISSION)
                        referrer['balance'] += commission
                        referrer['total_ref_bonus'] = referrer.get('total_ref_bonus', 0) + commission
                        try: await context.bot.send_message(target_p['ref_by'], f"🎁 Bạn nhận được `{commission:,}` hoa hồng từ cấp dưới nạp tiền!")
                        except: pass
                
                save_data(players)
                await query.edit_message_text(f"✅ Đã duyệt nạp `{amount:,}` cho {target_id}")
                try: await context.bot.send_message(target_id, f"✅ Nạp tiền thành công! +`{amount:,}` VNĐ.")
                except: pass

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    uid = str(user.id)
    p = get_player(user)

    # Xử lý đổi tiền cược
    if 'waiting_amt' in context.user_data:
        try:
            new_amt = int("".join(filter(str.isdigit, text)))
            game = context.user_data['waiting_amt']
            del context.user_data['waiting_amt']
            kb = game_xd_kb(new_amt) if game == "xd" else game_tx_kb(new_amt)
            await update.message.reply_text(f"✅ Đã đổi mức cược: `{new_amt:,}`", reply_markup=kb, parse_mode='Markdown')
        except: await update.message.reply_text("❌ Nhập số tiền hợp lệ.")

    # Xử lý rút tiền
    elif text.upper().startswith("RUT"):
        await update.message.reply_text("📝 Yêu cầu rút tiền đã được gửi tới Admin. Vui lòng chờ xử lý!")
        for aid in ADMIN_IDS:
            await context.bot.send_message(aid, f"🏧 YÊU CẦU RÚT:\nNgười dùng: {p['username']} ({uid})\nNội dung: {text}")

if __name__ == '__main__':
    if not BOT_TOKEN: print("Chưa có Token!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
        app.run_polling()
