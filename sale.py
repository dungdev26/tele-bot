import logging
import json
import os
import csv
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
)
# Thêm thư viện mạng để chống lag
from telegram.request import HTTPXRequest

# ================= CẤU HÌNH =================
TOKEN = 'Nhap_token_cua_ban_vao_day'
DATA_FILE = 'sales_data.json'
# ============================================

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- HÀM LƯU/ĐỌC FILE ---
def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi lưu file: {e}")

# --- XỬ LÝ DỮ LIỆU ---
def parse_line_data(line):
    line = line.strip()
    if not line: return None, "Dòng trống"
    if "-" in line: separator = "-"
    elif "," in line: separator = ","
    else: return None, "Thiếu dấu ngăn cách (-)"

    try:
        parts = line.split(separator)
        model = parts[0].strip().upper()
        imei = "---"
        customer = "Khách Lẻ"
        loai_khach = "LẺ"

        if len(parts) == 3:
            imei = parts[1].strip()
            customer_input = parts[2].strip().title()
        elif len(parts) == 2:
            part2 = parts[1].strip()
            if part2.isdigit() or len(part2) > 8: 
                imei = part2
                customer_input = "" 
            else:
                customer_input = part2.title()
        else:
            return None, "Sai định dạng"

        if customer_input:
            if "lẻ" in customer_input.lower() or "le" in customer_input.lower():
                customer = customer_input
                loai_khach = "LẺ"
            else:
                customer = customer_input
                loai_khach = "SỈ"

        now = datetime.now()
        return {
            'date': now.strftime("%d/%m"), 
            'time': now.strftime("%H:%M"),
            'model': model, 
            'imei': imei, 
            'customer': customer,
            'type': loai_khach 
        }, None
    except Exception:
        return None, "Lỗi không xác định"

# --- TÍNH NĂNG CHÍNH ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['/report', '/export'], ['/undo', '/clear']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🏪 **QUẢN LÝ BÁN HÀNG (BẢN FIX)** 🚀\n"
        "------------------------------\n"
        "📝 Nhập: `Tên Máy - IMEI - Khách`\n"
        "✏️ Sửa: `/sua [STT] [Nội dung]`\n"
        "❌ Xóa: `/xoa [STT]`",
        parse_mode='Markdown',
        reply_markup=reply_markup 
    )

async def log_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_text = update.message.text
    lines = full_text.strip().split('\n')
    saved_count = 0
    failed_lines = []
    current_data = load_data()

    for line in lines:
        entry, error = parse_line_data(line)
        if entry:
            current_data.append(entry)
            saved_count += 1
        else:
            failed_lines.append(f"{line} ({error})")

    if saved_count > 0:
        save_data(current_data)
        msg = f"✅ **ĐÃ LƯU {saved_count} MÁY!**\n"
        msg += "-"*20 + "\n"
        for item in current_data[-saved_count:]:
             msg += f"📱 {item['model']}\n"
        if failed_lines: msg += "\n⚠️ Lỗi: " + "; ".join(failed_lines)
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Sai cú pháp!", parse_mode='Markdown')

async def delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stt = int(context.args[0])
        current_data = load_data()
        if stt < 1 or stt > len(current_data):
            await update.message.reply_text(f"⚠️ Không có STT {stt}.")
            return
        removed = current_data.pop(stt - 1)
        save_data(current_data)
        await update.message.reply_text(f"🗑️ Đã xóa: {removed['model']}")
    except: await update.message.reply_text("⚠️ Ví dụ: `/xoa 2`", parse_mode='Markdown')

async def edit_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Ví dụ: `/sua 2 IP 15 - Tùng`", parse_mode='Markdown')
            return
        stt = int(context.args[0])
        new_content = " ".join(context.args[1:])
        current_data = load_data()
        if stt < 1 or stt > len(current_data):
            await update.message.reply_text(f"⚠️ Không có STT {stt}.")
            return
        new_entry, error = parse_line_data(new_content)
        if new_entry:
            current_data[stt-1] = new_entry
            save_data(current_data)
            await update.message.reply_text(f"✏️ Đã sửa dòng {stt}!\n✅ Mới: {new_entry['model']}")
        else:
            await update.message.reply_text(f"❌ Lỗi: {error}")
    except: await update.message.reply_text("⚠️ Lỗi cú pháp.", parse_mode='Markdown')

async def undo_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_data = load_data()
    if not current_data:
        await update.message.reply_text("📭 Trống.")
        return
    removed = current_data.pop()
    save_data(current_data)
    await update.message.reply_text(f"↩️ Đã xóa cuối: {removed['model']}")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current_data = load_data()
        if not current_data:
            await update.message.reply_text("📭 Chưa có đơn hàng.")
            return

        # SỬA LỖI KEY ERROR: Dùng .get('type', 'SỈ')
        list_le = [x for x in current_data if x.get('type', 'SỈ') == 'LẺ']
        list_si = [x for x in current_data if x.get('type', 'SỈ') != 'LẺ']
        
        final_msg = f"📅 <b>BÁO CÁO NGÀY {datetime.now().strftime('%d/%m')}</b>\n"

        if list_le:
            final_msg += "\n🛒 <b>KHÁCH LẺ</b>\n" + "="*15 + "\n"
            for i, item in enumerate(current_data, 1):
                # FIX LỖI TẠI ĐÂY
                if item.get('type', 'SỈ') == 'LẺ':
                    final_msg += f"<b>#{i}. {item['model']}</b>\n"
                    if item['imei'] != "---": final_msg += f"🔢 IMEI: <code>{item['imei']}</code>\n"
                    final_msg += f"👤 Khách: {item['customer']}\n---\n"

        if list_si:
            final_msg += "\n🚛 <b>KHÁCH SỈ</b>\n" + "="*15 + "\n"
            for i, item in enumerate(current_data, 1):
                # FIX LỖI TẠI ĐÂY
                if item.get('type', 'SỈ') != 'LẺ':
                    final_msg += f"<b>#{i}. {item['model']}</b>\n"
                    if item['imei'] != "---": final_msg += f"🔢 IMEI: <code>{item['imei']}</code>\n"
                    final_msg += f"👤 Khách: {item['customer']}\n---\n"

        final_msg += f"\n💰 <b>TỔNG:</b> {len(current_data)} Máy"

        if len(final_msg) > 4000:
            await update.message.reply_text("⚠️ Danh sách dài, đang gửi file Excel...")
            await export_csv(update, context)
        else:
            await update.message.reply_text(final_msg, parse_mode='HTML')
            
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {e}")

async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_data = load_data()
    if not current_data:
        await update.message.reply_text("📭 Trống.")
        return
    filename = f"DoanhThu_{datetime.now().strftime('%d_%m_%Y')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(["STT", "Phân Loại", "Ngày", "Giờ", "Tên Máy", "IMEI", "Khách Hàng"])
        for i, item in enumerate(current_data, 1):
            loai = item.get('type', 'SỈ')
            writer.writerow([i, loai, item.get('date',''), item['time'], item['model'], item['imei'], item['customer']])
    await update.message.reply_document(document=open(filename, 'rb'), caption="📂 File Excel")
    os.remove(filename)

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_data([]) 
    await update.message.reply_text("🗑️ Đã xóa sạch dữ liệu!")

# --- CHẠY BOT (CÓ CẤU HÌNH MẠNG FIX LAG) ---
if __name__ == '__main__':
    # Cấu hình mạng để không bị TimeOut trên Linux
    t_request = HTTPXRequest(
        connection_pool_size=10, 
        read_timeout=60.0, 
        write_timeout=60.0, 
        connect_timeout=60.0, 
        pool_timeout=60.0
    )
    
    application = ApplicationBuilder().token(TOKEN).request(t_request).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('report', report))
    application.add_handler(CommandHandler('undo', undo_last))
    application.add_handler(CommandHandler('export', export_csv))
    application.add_handler(CommandHandler('clear', clear_data))
    application.add_handler(CommandHandler('xoa', delete_item))
    application.add_handler(CommandHandler('sua', edit_item))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), log_sale))
    
    print("🚀 Bot (Code cũ - Đã fix lỗi) đang chạy...")
    
    # Vòng lặp bất tử để không bao giờ sập
    while True:
        try:
            application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Mạng lag: {e}. Thử lại sau 3s...")
            time.sleep(3) 
            continue