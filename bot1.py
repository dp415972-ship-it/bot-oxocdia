import logging
import json
import os
import random
import asyncio
import uuid
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters,
    Application
)
from telegram.constants import ParseMode

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [8393067202]  # Thêm ID Telegram của các Admin vào đây
ADMIN_USERNAME = "@admin_casino_pro" 
BANK_INFO = {
    "name": "MBBank",
    "stk": "144881",
    "owner": "NGUYEN VAN A"
}

DATA_FILE = 'database.json'

# --- CONSTANTS ---
INITIAL_BALANCE = 10000     # Tiền chơi thử
MIN_BET = 1000              # Cược tối thiểu
MAX_BET = 100000000         # Cược tối đa
MIN_WITHDRAW = 100000       # Rút tối thiểu
REF_COMMISSION = 0.10       # Hoa hồng 10%
DAILY_BONUS = 5000          # Tiền điểm danh

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- DATABASE LAYER ---
class Database:
    def __init__(self, filename):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading DB: {e}")
                return self.get_empty_schema()
        return self.get_empty_schema()

    def get_empty_schema(self):
        return {
            "players": {},
            "transactions": [],
            "game_stats": {"total_vol": 0, "total_payout": 0},
            "global_config": {"maintenance": False}
        }

    def save(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Error saving DB: {e}")

    def get_player(self, user, ref_id=None):
        uid = str(user.id)
        if uid not in self.data["players"]:
            self.data["players"][uid] = {
                "id": user.id,
                "username": user.username or user.first_name,
                "balance": INITIAL_BALANCE,
                "total_deposit": 0,
                "total_withdraw": 0,
                "total_bet": 0,
                "total_win": 0,
                "ref_by": ref_id if (ref_id and ref_id != uid and ref_id in self.data["players"]) else None,
                "ref_count": 0,
                "ref_earnings": 0,
                "last_checkin": None,
                "status": "active", # active, banned
                "history": [],
                "created_at": datetime.now().isoformat()
            }
            if ref_id and ref_id in self.data["players"]:
                self.data["players"][ref_id]["ref_count"] += 1
            self.save()
        return self.data["players"][uid]

    def update_balance(self, uid, amount):
        uid = str(uid)
        if uid in self.data["players"]:
            self.data["players"][uid]["balance"] += amount
            self.save()
            return True
        return False

db = Database(DATA_FILE)

# --- GAME LOGIC ENGINES ---
class GameEngine:
    @staticmethod
    def roll_xoc_dia():
        items = [random.choice(['⚪️', '🔴']) for _ in range(4)]
        reds = items.count('🔴')
        outcome = "chan" if reds % 2 == 0 else "le"
        detail = {4: "4do", 0: "4trang", 3: "3do", 1: "3trang"}.get(reds)
        return items, outcome, detail

    @staticmethod
    def roll_tai_xiu():
        dices = [random.randint(1, 6) for _ in range(3)]
        total = sum(dices)
        if dices[0] == dices[1] == dices[2]:
            return dices, total, "triple"
        return dices, total, "tai" if total >= 11 else "xiu"

    @staticmethod
    def deal_baccarat():
        def get_card(): return random.randint(1, 13)
        def card_val(n): return n if n < 10 else 0
        
        p_hand = [get_card(), get_card()]
        b_hand = [get_card(), get_card()]
        
        p_score = sum(card_val(c) for c in p_hand) % 10
        b_score = sum(card_val(c) for c in b_hand) % 10
        
        # Third card rules (simplified for bot)
        if p_score < 6:
            p_hand.append(get_card())
            p_score = sum(card_val(c) for c in p_hand) % 10
            
        if b_score < 6:
            b_hand.append(get_card())
            b_score = sum(card_val(c) for c in b_hand) % 10
            
        if p_score > b_score: result = "player"
        elif b_score > p_score: result = "banker"
        else: result = "tie"
        
        return p_hand, b_hand, p_score, b_score, result

# --- UI INTERFACE ---
class UIManager:
    @staticmethod
    def format_money(n):
        return "{:,.0f}".format(n)

    @staticmethod
    def main_menu(player):
        kb = [
            [InlineKeyboardButton("🎮 SẢNH TRÒ CHƠI", callback_data="view_lobby")],
            [InlineKeyboardButton("💳 NẠP TIỀN", callback_data="view_deposit"), InlineKeyboardButton("🏧 RÚT TIỀN", callback_data="view_withdraw")],
            [InlineKeyboardButton("🎁 NHIỆM VỤ", callback_data="view_tasks"), InlineKeyboardButton("👥 ĐẠI LÝ", callback_data="view_affiliate")],
            [InlineKeyboardButton("👤 TÀI KHOẢN", callback_data="view_profile"), InlineKeyboardButton("📊 LỊCH SỬ", callback_data="view_history")],
            [InlineKeyboardButton("☎️ HỖ TRỢ TRỰC TUYẾN", url=f"https://t.me/{ADMIN_USERNAME[1:]}")]
        ]
        return InlineKeyboardMarkup(kb)

    @staticmethod
    def lobby_menu():
        kb = [
            [InlineKeyboardButton("🎲 XÓC ĐĨA VIP", callback_data="game_xd_init"), InlineKeyboardButton("🔥 TÀI XỈU SICBO", callback_data="game_tx_init")],
            [InlineKeyboardButton("🃏 BACCARAT", callback_data="game_bc_init"), InlineKeyboardButton("🎰 MINI SLOT", callback_data="game_slot_init")],
            [InlineKeyboardButton("🔙 QUAY LẠI MENU CHÍNH", callback_data="view_main")]
        ]
        return InlineKeyboardMarkup(kb)

    @staticmethod
    def xd_keyboard(bet_amt):
        kb = [
            [InlineKeyboardButton(f"💰 MỨC CƯỢC: {UIManager.format_money(bet_amt)} (Sửa)", callback_data="input_bet_xd")],
            [InlineKeyboardButton("CHẴN x1.96", callback_data=f"play_xd_chan_{bet_amt}"), InlineKeyboardButton("LẺ x1.96", callback_data=f"play_xd_le_{bet_amt}")],
            [InlineKeyboardButton("3 TRẮNG x3.8", callback_data=f"play_xd_3trang_{bet_amt}"), InlineKeyboardButton("3 ĐỎ x3.8", callback_data=f"play_xd_3do_{bet_amt}")],
            [InlineKeyboardButton("4 TRẮNG x15", callback_data=f"play_xd_4trang_{bet_amt}"), InlineKeyboardButton("4 ĐỎ x15", callback_data=f"play_xd_4do_{bet_amt}")],
            [InlineKeyboardButton("🔙 VỀ SẢNH", callback_data="view_lobby")]
        ]
        return InlineKeyboardMarkup(kb)

    @staticmethod
    def tx_keyboard(bet_amt):
        kb = [
            [InlineKeyboardButton(f"💰 MỨC CƯỢC: {UIManager.format_money(bet_amt)} (Sửa)", callback_data="input_bet_tx")],
            [InlineKeyboardButton("TÀI x1.96", callback_data=f"play_tx_tai_{bet_amt}"), InlineKeyboardButton("XỈU x1.96", callback_data=f"play_tx_xiu_{bet_amt}")],
            [InlineKeyboardButton("BÃO (TRIPLE x35)", callback_data=f"play_tx_triple_{bet_amt}")],
            [InlineKeyboardButton("🔙 VỀ SẢNH", callback_data="view_lobby")]
        ]
        return InlineKeyboardMarkup(kb)

# --- CORE HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref_id = context.args[0].replace("ref_", "") if context.args and "ref_" in context.args[0] else None
    player = db.get_player(user, ref_id)
    
    msg = (
        f"👋 Chào mừng **{player['username']}** đến với **Luxury Casino Pro**!\n\n"
        f"💰 Số dư: `{UIManager.format_money(player['balance'])} VNĐ`\n"
        f"🏆 Thành viên: `Vip Member`\n"
        f"🔗 ID của bạn: `{user.id}`\n\n"
        f"Hệ thống nạp rút tự động, minh bạch 100%. Chúc bạn may mắn!"
    )
    
    if update.message:
        await update.message.reply_text(msg, reply_markup=UIManager.main_menu(player), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=UIManager.main_menu(player), parse_mode=ParseMode.MARKDOWN)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = update.effective_user
    player = db.get_player(user)
    await query.answer()

    # --- NAVIGATION ---
    if data == "view_main":
        await start_command(update, context)
    elif data == "view_lobby":
        await query.edit_message_text("🎮 **SẢNH TRÒ CHƠI CASINO**\n\nVui lòng chọn loại hình giải trí:", 
                                     reply_markup=UIManager.lobby_menu(), parse_mode=ParseMode.MARKDOWN)
    
    # --- GAME XOC DIA ---
    elif data == "game_xd_init":
        bet = context.user_data.get('bet_xd', 10000)
        await query.edit_message_text(f"🎲 **XÓC ĐĨA VIP ONLINE**\n\nSố dư: `{UIManager.format_money(player['balance'])}` VNĐ\nChọn cửa đặt:", 
                                     reply_markup=UIManager.xd_keyboard(bet), parse_mode=ParseMode.MARKDOWN)

    elif data == "input_bet_xd":
        context.user_data['state'] = "wait_bet_xd"
        await query.message.reply_text("🔢 Nhập số tiền cược bạn muốn đặt cho mỗi ván Xóc Đĩa:")

    elif data.startswith("play_xd_"):
        parts = data.split("_")
        choice, amt = parts[2], int(parts[3])
        
        if player['balance'] < amt:
            return await query.message.reply_text("❌ Tài khoản của bạn không đủ số dư để thực hiện ván cược này.")
        
        player['balance'] -= amt
        visuals, out, detail = GameEngine.roll_xoc_dia()
        
        win = False
        mult = 0
        if choice in ['chan', 'le']:
            if choice == out: win, mult = True, 1.96
        else:
            if choice == detail: win, mult = True, (3.8 if "3" in choice else 15)
        
        res_text = f"🎲 Kết quả: `{' '.join(visuals)}` ➜ **{out.upper()}**\n"
        if win:
            win_amt = int(amt * mult)
            player['balance'] += win_amt
            player['total_win'] += win_amt
            res_text += f"✨ **THẮNG:** `+{UIManager.format_money(win_amt)}` VNĐ"
        else:
            res_text += f"💀 **THUA:** `-{UIManager.format_money(amt)}` VNĐ"
        
        db.save()
        await query.edit_message_text(f"{res_text}\n💰 Số dư: `{UIManager.format_money(player['balance'])}`", 
                                     reply_markup=UIManager.xd_keyboard(amt), parse_mode=ParseMode.MARKDOWN)

    # --- GAME TAI XIU ---
    elif data == "game_tx_init":
        bet = context.user_data.get('bet_tx', 10000)
        await query.edit_message_text(f"🔥 **TÀI XỈU SICBO QUỐC TẾ**\n\nSố dư: `{UIManager.format_money(player['balance'])}` VNĐ", 
                                     reply_markup=UIManager.tx_keyboard(bet), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("play_tx_"):
        parts = data.split("_")
        choice, amt = parts[2], int(parts[3])
        
        if player['balance'] < amt: return await query.message.reply_text("❌ Số dư không đủ!")
        
        player['balance'] -= amt
        dices, total, out = GameEngine.roll_tai_xiu()
        win = (choice == out)
        mult = 35 if choice == "triple" else 1.96
        
        res_text = f"🔥 Kết quả: `{' + '.join(map(str, dices))} = {total}` ➜ **{out.upper()}**\n"
        if win:
            win_amt = int(amt * mult)
            player['balance'] += win_amt
            res_text += f"✨ **THẮNG:** `+{UIManager.format_money(win_amt)}`"
        else:
            res_text += f"💀 **THUA:** `-{UIManager.format_money(amt)}`"
        
        db.save()
        await query.edit_message_text(f"{res_text}\n💰 Số dư: `{UIManager.format_money(player['balance'])}`", 
                                     reply_markup=UIManager.tx_keyboard(amt), parse_mode=ParseMode.MARKDOWN)

    # --- SYSTEM: AFFILIATE (DAI LY) ---
    elif data == "view_affiliate":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"
        msg = (
            f"👥 **HỆ THỐNG ĐẠI LÝ & CTV**\n\n"
            f"Hãy mời bạn bè tham gia để nhận hoa hồng vĩnh viễn!\n"
            f"💰 Hoa hồng: **{int(REF_COMMISSION*100)}%** giá trị mỗi lần cấp dưới nạp tiền.\n\n"
            f"📊 Thống kê của bạn:\n"
            f"▫️ Cấp dưới: `{player['ref_count']} thành viên`\n"
            f"▫️ Tổng hoa hồng: `{UIManager.format_money(player['ref_earnings'])}` VNĐ\n\n"
            f"🔗 Link mời của bạn:\n`{link}`"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_main")]]), parse_mode=ParseMode.MARKDOWN)

    # --- SYSTEM: DEPOSIT (NAP TIEN) ---
    elif data == "view_deposit":
        msg = (
            f"💳 **NẠP TIỀN VÀO TÀI KHOẢN**\n\n"
            f"Vui lòng chọn số tiền bạn muốn nạp để nhận QR thanh toán:"
        )
        btns = [
            [InlineKeyboardButton("50,000", callback_data="act_dep_50000"), InlineKeyboardButton("100,000", callback_data="act_dep_100000")],
            [InlineKeyboardButton("500,000", callback_data="act_dep_500000"), InlineKeyboardButton("1,000,000", callback_data="act_dep_1000000")],
            [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_main")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("act_dep_"):
        amt = int(data.split("_")[2])
        qr_url = f"https://img.vietqr.io/image/{BANK_INFO['name']}-{BANK_INFO['stk']}-compact.jpg?amount={amt}&addInfo=NAP%20{user.id}"
        
        await query.message.reply_photo(
            photo=qr_url,
            caption=(
                f"🏦 **THÔNG TIN THANH TOÁN**\n\n"
                f"Chủ TK: `{BANK_INFO['owner']}`\n"
                f"STK: `{BANK_INFO['stk']}`\n"
                f"Ngân hàng: `{BANK_INFO['name']}`\n"
                f"Số tiền: `{UIManager.format_money(amt)}` VNĐ\n"
                f"Nội dung: `NAP {user.id}`\n\n"
                f"📌 *Lưu ý: Chuyển đúng nội dung để được duyệt tự động.*"
            )
        )
        # Thông báo Admin
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(aid, f"🔔 **YÊU CẦU NẠP:**\nUser: {player['username']} ({user.id})\nSố tiền: {UIManager.format_money(amt)}",
                                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("DUYỆT ✅", callback_data=f"adm_pay_appr_{user.id}_{amt}")]]))
            except: pass

    # --- ADMIN ACTIONS ---
    elif data.startswith("adm_pay_appr_"):
        if user.id not in ADMIN_IDS: return
        _, _, _, target_id, amount = data.split("_")
        amount = int(amount)
        
        target = db.data["players"].get(target_id)
        if target:
            target["balance"] += amount
            target["total_deposit"] += amount
            
            # Xử lý hoa hồng cấp trên
            if target.get("ref_by"):
                parent = db.data["players"].get(target["ref_by"])
                if parent:
                    comm = int(amount * REF_COMMISSION)
                    parent["balance"] += comm
                    parent["ref_earnings"] += comm
                    try: await context.bot.send_message(target["ref_by"], f"🎁 Bạn nhận được `{UIManager.format_money(comm)}` hoa hồng nạp tiền từ cấp dưới!")
                    except: pass
            
            db.save()
            await query.edit_message_text(f"✅ Đã duyệt nạp `{UIManager.format_money(amount)}` cho ID {target_id}")
            try: await context.bot.send_message(target_id, f"✅ Nạp tiền thành công! Số dư hiện tại: `{UIManager.format_money(target['balance'])}` VNĐ.")
            except: pass

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    state = context.user_data.get('state')
    
    if state == "wait_bet_xd":
        try:
            val = int("".join(filter(str.isdigit, text)))
            if val < MIN_BET: return await update.message.reply_text(f"❌ Cược tối thiểu là {MIN_BET}")
            context.user_data['bet_xd'] = val
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ Đã đổi mức cược Xóc Đĩa thành: `{UIManager.format_money(val)}`", 
                                            reply_markup=UIManager.xd_keyboard(val), parse_mode=ParseMode.MARKDOWN)
        except: pass

    elif text.upper().startswith("RUT"):
        player = db.get_player(user)
        try:
            amt = int(text.split(" ")[1])
            if amt < MIN_WITHDRAW: return await update.message.reply_text(f"❌ Rút tối thiểu {MIN_WITHDRAW}")
            if player['balance'] < amt: return await update.message.reply_text("❌ Số dư không đủ!")
            
            player['balance'] -= amt
            db.save()
            await update.message.reply_text("📝 Yêu cầu rút tiền đã được gửi. Admin sẽ xử lý trong 5-30 phút.")
            for aid in ADMIN_IDS:
                await context.bot.send_message(aid, f"🏧 **YÊU CẦU RÚT:**\nUser: {player['username']} ({user.id})\nSố tiền: {UIManager.format_money(amt)}\nNội dung: {text}")
        except: await update.message.reply_text("⚠️ Cú pháp rút: `RUT [Số tiền] [STK] [Ngân hàng]`")

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    if not BOT_TOKEN:
        print("LỖI: Chưa có BOT_TOKEN!")
    else:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CallbackQueryHandler(callback_router))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
        
        print("Bot Casino v4 đã khởi động...")
        application.run_polling()
