import logging
import json
import os
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)
from telegram.constants import ParseMode

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [8393067202]
ADMIN_USERNAME = "@admin_casino_pro" 
BANK_INFO = {
    "name": "MBBank",
    "stk": "144881",
    "owner": "NGUYEN VAN A"
}
DATA_FILE = 'database.json'

# --- CONSTANTS ---
INITIAL_BALANCE = 50000     
MIN_BET = 1000              
REF_COMMISSION = 0.10       
DAILY_BONUS = 5000          

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DATABASE ---
class Database:
    def __init__(self, filename):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return self.get_empty_schema()
        return self.get_empty_schema()

    def get_empty_schema(self):
        return {"players": {}, "transactions": []}

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def get_player(self, user, ref_id=None):
        uid = str(user.id)
        if uid not in self.data["players"]:
            self.data["players"][uid] = {
                "id": user.id,
                "username": user.username or user.first_name,
                "balance": INITIAL_BALANCE,
                "total_deposit": 0,
                "total_bet": 0,
                "total_win": 0,
                "ref_by": ref_id if (ref_id and ref_id != uid and ref_id in self.data["players"]) else None,
                "ref_count": 0,
                "ref_earnings": 0,
                "last_checkin": None,
                "history": []
            }
            if ref_id and ref_id in self.data["players"]:
                self.data["players"][ref_id]["ref_count"] += 1
            self.save()
        return self.data["players"][uid]

db = Database(DATA_FILE)

# --- GAME LOGIC ---
class GameEngine:
    @staticmethod
    def roll_xoc_dia():
        items = [random.choice(['⚪️', '🔴']) for _ in range(4)]
        reds = items.count('🔴')
        outcome = "chan" if reds % 2 == 0 else "le"
        detail = {4: "4do", 0: "4trang", 3: "3do", 1: "3trang"}.get(reds, "2do2trang")
        return items, outcome, detail

    @staticmethod
    def roll_tai_xiu():
        dices = [random.randint(1, 6) for _ in range(3)]
        total = sum(dices)
        if dices[0] == dices[1] == dices[2]: return dices, total, "triple"
        return dices, total, "tai" if total >= 11 else "xiu"

    @staticmethod
    def play_slot():
        icons = ["🍎", "🍊", "🍇", "🔔", "💎", "7️⃣"]
        result = [random.choice(icons) for _ in range(3)]
        if result[0] == result[1] == result[2]:
            return result, 10 if result[0] == "7️⃣" else 5
        if result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            return result, 2
        return result, 0

# --- UI MANAGER ---
class UIManager:
    @staticmethod
    def format_money(n): return "{:,.0f}".format(n)

    @staticmethod
    def main_menu(player):
        kb = [
            [InlineKeyboardButton("🎮 SẢNH TRÒ CHƠI", callback_data="view_lobby")],
            [InlineKeyboardButton("💳 NẠP TIỀN", callback_data="view_deposit"), InlineKeyboardButton("🏧 RÚT TIỀN", callback_data="view_withdraw")],
            [InlineKeyboardButton("🎁 NHIỆM VỤ", callback_data="view_tasks"), InlineKeyboardButton("👥 ĐẠI LÝ", callback_data="view_affiliate")],
            [InlineKeyboardButton("👤 TÀI KHOẢN", callback_data="view_profile"), InlineKeyboardButton("📊 LỊCH SỬ", callback_data="view_history")]
        ]
        return InlineKeyboardMarkup(kb)

    @staticmethod
    def lobby_menu():
        kb = [
            [InlineKeyboardButton("🎲 XÓC ĐĨA", callback_data="game_xd_lobby"), InlineKeyboardButton("🔥 TÀI XỈU", callback_data="game_tx_lobby")],
            [InlineKeyboardButton("🎰 MINI SLOT", callback_data="game_slot_lobby"), InlineKeyboardButton("🃏 BACCARAT", callback_data="game_bc_lobby")],
            [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_main")]
        ]
        return InlineKeyboardMarkup(kb)

# --- HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref_id = context.args[0].replace("ref_", "") if context.args and "ref_" in context.args[0] else None
    player = db.get_player(user, ref_id)
    msg = f"👋 Chào **{player['username']}**\n💰 Số dư: `{UIManager.format_money(player['balance'])}` VNĐ\nHệ thống Casino uy tín hàng đầu Telegram."
    
    if update.message: await update.message.reply_text(msg, reply_markup=UIManager.main_menu(player), parse_mode=ParseMode.MARKDOWN)
    else: await update.callback_query.edit_message_text(msg, reply_markup=UIManager.main_menu(player), parse_mode=ParseMode.MARKDOWN)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = update.effective_user
    player = db.get_player(user)
    await query.answer()

    if data == "view_main": await start_command(update, context)
    elif data == "view_lobby":
        await query.edit_message_text("🎮 **SẢNH TRÒ CHƠI**", reply_markup=UIManager.lobby_menu(), parse_mode=ParseMode.MARKDOWN)
    
    # --- XOC DIA LOBBY ---
    elif data == "game_xd_lobby":
        kb = [
            [InlineKeyboardButton("CHẴN (x1.96)", callback_data="bet_xd_chan"), InlineKeyboardButton("LẺ (x1.96)", callback_data="bet_xd_le")],
            [InlineKeyboardButton("3 TRẮNG (x3.8)", callback_data="bet_xd_3trang"), InlineKeyboardButton("3 ĐỎ (x3.8)", callback_data="bet_xd_3do")],
            [InlineKeyboardButton("4 TRẮNG (x15)", callback_data="bet_xd_4trang"), InlineKeyboardButton("4 ĐỎ (x15)", callback_data="bet_xd_4do")],
            [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_lobby")]
        ]
        await query.edit_message_text(f"🎲 **XÓC ĐĨA**\nSố dư: `{UIManager.format_money(player['balance'])}` VNĐ\nChọn cửa muốn đặt:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    # --- TAI XIU LOBBY ---
    elif data == "game_tx_lobby":
        kb = [
            [InlineKeyboardButton("TÀI (x1.96)", callback_data="bet_tx_tai"), InlineKeyboardButton("XỈU (x1.96)", callback_data="bet_tx_xiu")],
            [InlineKeyboardButton("BÃO (x35)", callback_data="bet_tx_triple")],
            [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_lobby")]
        ]
        await query.edit_message_text(f"🔥 **TÀI XỈU**\nSố dư: `{UIManager.format_money(player['balance'])}` VNĐ\nChọn cửa muốn đặt:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    # --- INPUT BET TRIGGER ---
    elif data.startswith("bet_"):
        game_type, door = data.split("_")[1], data.split("_")[2]
        context.user_data['bet_flow'] = {"type": game_type, "door": door}
        context.user_data['state'] = "wait_amount"
        await query.message.reply_text(f"🎯 Bạn chọn đặt cửa: **{door.upper()}**\n👉 Vui lòng nhập số tiền muốn cược (Ví dụ: 10000):")

    # --- PROFILE & TASKS ---
    elif data == "view_profile":
        msg = (f"👤 **THÔNG TIN TÀI KHOẢN**\n\n"
               f"ID: `{user.id}`\nSố dư: `{UIManager.format_money(player['balance'])}` VNĐ\n"
               f"Tổng nạp: `{UIManager.format_money(player['total_deposit'])}` VNĐ\n"
               f"Tổng cược: `{UIManager.format_money(player['total_bet'])}` VNĐ")
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_main")]]), parse_mode=ParseMode.MARKDOWN)

    elif data == "view_tasks":
        kb = [[InlineKeyboardButton("📆 ĐIỂM DANH HÀNG NGÀY", callback_data="act_checkin")], [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="view_main")]]
        await query.edit_message_text("🎁 **NHIỆM VỤ & QUÀ TẶNG**\nĐiểm danh mỗi ngày để nhận tiền miễn phí!", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "act_checkin":
        today = datetime.now().strftime("%Y-%m-%d")
        if player.get("last_checkin") == today:
            await query.message.reply_text("❌ Hôm nay bạn đã điểm danh rồi!")
        else:
            player["last_checkin"] = today
            player["balance"] += DAILY_BONUS
            db.save()
            await query.message.reply_text(f"✅ Điểm danh thành công! Bạn nhận được +{UIManager.format_money(DAILY_BONUS)} VNĐ")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    player = db.get_player(user)
    
    if context.user_data.get('state') == "wait_amount":
        try:
            amount = int("".join(filter(str.isdigit, text)))
            if amount < MIN_BET: return await update.message.reply_text(f"❌ Cược tối thiểu là {MIN_BET}")
            if player['balance'] < amount: return await update.message.reply_text("❌ Số dư không đủ!")
            
            flow = context.user_data.get('bet_flow')
            player['balance'] -= amount
            player['total_bet'] += amount
            context.user_data['state'] = None # Reset state
            
            # --- LOGIC XỬ LÝ KẾT QUẢ ---
            if flow['type'] == "xd":
                items, out, detail = GameEngine.roll_xoc_dia()
                win = (flow['door'] == out) if flow['door'] in ['chan', 'le'] else (flow['door'] == detail)
                mult = 1.96 if flow['door'] in ['chan', 'le'] else (15 if "4" in flow['door'] else 3.8)
                res_msg = f"🎲 Kết quả: `{' '.join(items)}` -> **{out.upper()}**\n"
            else: # Tai Xiu
                dices, total, out = GameEngine.roll_tai_xiu()
                win = (flow['door'] == out)
                mult = 35 if flow['door'] == "triple" else 1.96
                res_msg = f"🔥 Kết quả: `{' + '.join(map(str, dices))} = {total}` -> **{out.upper()}**\n"

            if win:
                win_amt = int(amount * mult)
                player['balance'] += win_amt
                player['total_win'] += win_amt
                res_msg += f"✨ **THẮNG:** `+{UIManager.format_money(win_amt)}` VNĐ"
            else:
                res_msg += f"💀 **THUA:** `-{UIManager.format_money(amount)}` VNĐ"
            
            db.save()
            await update.message.reply_text(res_msg, parse_mode=ParseMode.MARKDOWN)
            await start_command(update, context) # Show main menu again
            
        except ValueError:
            await update.message.reply_text("⚠️ Vui lòng nhập một số tiền hợp lệ!")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("LỖI: Chưa có BOT_TOKEN!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CallbackQueryHandler(callback_router))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
        print("Bot Casino v5 is running...")
        app.run_polling()
