import logging
import json
import os
import csv
from datetime import datetime
from telegram import Update
# Thêm thư viện HTTPXRequest để chỉnh mạng
from telegram.request import HTTPXRequest 
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
)

# ================= CẤU HÌNH =================
# Ưu tiên lấy Token từ biến môi trường của Server, nếu không có thì dùng Token cứng
# Lưu ý: Trên Render nhớ đặt biến môi trường tên là TOKEN
TOKEN = os.environ.get("TOKEN", '8587238169:AAEeHUWJRPKsXAzT0hHEo83xgfTWw8gnZGw')
DATA_FILE = 'sales_data.json'
# ============================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HÀM LƯU/ĐỌC FILE ---
def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- CÁC TÍNH NĂNG CHÍNH (GIỮ NGUYÊN CỦA BẠN) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome Boss!**\n\n"
        "⚡ **BULK IMPORT MODE ACTIVATED**\n"
        "You can send multiple lines at once:\n\n"
        "`iPhone 15 - 111 - Mr A`\n"
        "`Samsung - 222`\n"
        "`Oppo - 333 - Ms B`\n\n"
        "🛠 **Commands:**\n"
        "/undo - Delete last entry\n"
        "/report - View list\n"
        "/export - Download Excel file\n"
        "/clear - Delete all",
        parse_mode='Markdown'
    )

async def log_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_text = update.message.text
    
    # Tách tin nhắn thành từng dòng (dựa vào phím Enter)
    lines = full_text.strip().split('\n')
    
    saved_count = 0
    failed_lines = []
    
    current_data = load_data()
    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M:%S")

    # Chạy vòng lặp qua từng dòng để xử lý
    for line in lines:
        line = line.strip()
        if not line: continue # Bỏ qua dòng trống

        # Logic nhận diện dấu phân cách cho từng dòng
        if "-" in line: separator = "-"
        elif "," in line: separator = ","
        else:
            failed_lines.append(f"{line} (No separator)")
            continue

        try:
            parts = line.split(separator)
            
            # Yêu cầu tối thiểu phải có: Tên máy và IMEI (2 phần)
            if len(parts) < 2:
                failed_lines.append(line)
                continue

            model = parts[0].strip().upper()
            imei = parts[1].strip()
            # Nếu có phần thứ 3 thì là tên khách, không thì là 'Walk-in Customer'
            customer = parts[2].strip().title() if len(parts) > 2 else "Walk-in Customer"

            entry = {
                'date': date_str,
                'time': time_str,
                'model': model,
                'imei': imei,
                'customer': customer
            }
            
            current_data.append(entry)
            saved_count += 1
            
        except Exception:
            failed_lines.append(line)

    # Lưu dữ liệu sau khi xử lý xong hết các dòng
    if saved_count > 0:
        save_data(current_data)
        
        msg = f"✅ **SAVED {saved_count} ITEMS!**\n"
        msg += "------------------------\n"
        # Chỉ hiển thị 5 dòng cuối cùng vừa nhập để tránh spam tin nhắn quá dài
        for item in current_data[-saved_count:]:
            msg += f"📦 {item['model']} - {item['customer']}\n"
        
        msg += f"\n🕒 Time: `{time_str}`"
        
        if failed_lines:
            msg += "\n\n⚠️ **Failed lines (ignored):**\n"
            msg += "\n".join(failed_lines)
            
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    else:
        # Nếu không dòng nào lưu được
        await update.message.reply_text(
            "❌ **Format Error!**\n"
            "Please check your input. Each line must look like:\n"
            "`Model - IMEI` or `Model - IMEI - Customer`",
            parse_mode='Markdown'
        )

async def undo_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_data = load_data()
    if not current_data:
        await update.message.reply_text("📭 Nothing to undo.")
        return

    removed = current_data.pop()
    save_data(current_data)
    
    await update.message.reply_text(
        f"↩️ **Undone:** {removed['model']} - {removed.get('customer', 'Unknown')}",
        parse_mode='Markdown'
    )

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_data = load_data()
    if not current_data:
        await update.message.reply_text("📭 List is empty.")
        return

    msg = f"📅 **REPORT ({datetime.now().strftime('%d/%m/%Y')})**\n"
    msg += "========================\n"
    for i, item in enumerate(current_data, 1):
        cust = item.get('customer', 'Walk-in Customer')
        msg += f"{i}. **{item['model']}**\n   └ `{item['imei']}`\n   └ 👤 {cust}\n"
    msg += "========================\n"
    msg += f"💰 **Total:** {len(current_data)} items"
    
    if len(msg) > 4000:
        await update.message.reply_text("⚠️ Report is too long! Please use /export to view full list.")
        await export_csv(update, context)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_data = load_data()
    if not current_data:
        await update.message.reply_text("📭 No data to export.")
        return

    filename = f"Sales_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(["No.", "Date", "Time", "Model", "IMEI", "Customer"])
        for i, item in enumerate(current_data, 1):
            writer.writerow([
                i, 
                item.get('date', ''), 
                item['time'], 
                item['model'], 
                item['imei'], 
                item.get('customer', 'Walk-in Customer')
            ])
    
    await update.message.reply_document(document=open(filename, 'rb'), caption="📊 Detailed Report")
    os.remove(filename)

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_data([]) 
    await update.message.reply_text("🗑️ **All data cleared!**", parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(f"⚠️ Bot Error: {context.error}")

# =========================================================================
# PHẦN CHÍNH: TỰ ĐỘNG CHUYỂN WEBHOOK (CHO RENDER) HOẶC POLLING (MÁY NHÀ)
# =========================================================================
if __name__ == '__main__':
    # Cấu hình request timeout để tránh lỗi mạng chập chờn
    t_request = HTTPXRequest(connection_pool_size=8, read_timeout=60, write_timeout=60, connect_timeout=60)

    application = ApplicationBuilder().token(TOKEN).request(t_request).build()
    
    # Đăng ký các lệnh
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('report', report))
    application.add_handler(CommandHandler('undo', undo_last))
    application.add_handler(CommandHandler('export', export_csv))
    application.add_handler(CommandHandler('clear', clear_data))
    
    # Đăng ký xử lý tin nhắn (Loại trừ lệnh)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), log_sale))
    application.add_error_handler(error_handler)
    
    # --- KIỂM TRA MÔI TRƯỜNG ĐỂ CHỌN CÁCH CHẠY ---
    # Render luôn cung cấp biến môi trường RENDER_EXTERNAL_URL
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL') 
    
    if RENDER_URL:
        # >>> CHẠY TRÊN SERVER (RENDER) <<<
        PORT = int(os.environ.get("PORT", "8080"))
        print(f"🚀 Bot starting on Render (Webhook Mode) at {RENDER_URL} on Port {PORT}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{RENDER_URL}/{TOKEN}"
        )
    else:
        # >>> CHẠY TRÊN MÁY TÍNH CÁ NHÂN <<<
        print("💻 Bot starting on Local Machine (Polling Mode)...")
        application.run_polling(poll_interval=1.0)