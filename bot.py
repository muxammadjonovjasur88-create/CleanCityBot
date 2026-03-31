import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters
from database import Database

logging.basicConfig(format="%(asctime)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_PHOTO, WAITING_LOCATION, WAITING_DESCRIPTION = range(3)

# ===== SHU YERGA O'Z MA'LUMOTLARINGIZNI YOZING =====
BOT_TOKEN = "TOKEN_YOZING"       # BotFather dan olgan token
ADMIN_IDS = [123456789]          # @userinfobot dan olgan ID
# ====================================================

db = Database()

STATUS_TEXT = {
    "pending":   "⏳ Under Review",
    "approved":  "✅ Approved — Truck Dispatched",
    "rejected":  "❌ Rejected",
    "completed": "🏁 Completed",
}

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📸 Report a Trash Bin")],
        [KeyboardButton("📋 My Reports"), KeyboardButton("ℹ️ Help")],
    ], resize_keyboard=True)

def location_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📍 Share My Location", request_location=True)],
        [KeyboardButton("❌ Cancel")],
    ], resize_keyboard=True)

def admin_buttons(report_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve & Dispatch Truck", callback_data=f"approve_{report_id}")],
        [
            InlineKeyboardButton("❌ Reject",    callback_data=f"reject_{report_id}"),
            InlineKeyboardButton("👁 Seen",      callback_data=f"seen_{report_id}"),
            InlineKeyboardButton("🏁 Complete",  callback_data=f"complete_{report_id}"),
        ],
    ])

async def notify_admins(context, report):
    maps = f"https://maps.google.com/?q={report['lat']},{report['lon']}"
    caption = (
        f"🚨 <b>NEW REPORT #{report['id']}</b>\n"
        f"👤 {report['full_name']} (@{report.get('username') or 'N/A'})\n"
        f"📍 <a href='{maps}'>View on Map</a>\n"
        f"💬 {report.get('description') or '—'}\n"
        f"🕐 {report['created_at']}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=report["photo_id"],
                caption=caption, parse_mode="HTML",
                reply_markup=admin_buttons(report["id"]),
            )
        except Exception as e:
            logger.warning("Admin notify error: %s", e)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user.id, user.full_name, user.username)
    await update.message.reply_text(
        f"👋 Hello, <b>{user.first_name}</b>!\n\n"
        "🗑️ Welcome to <b>CleanCity Bot</b>!\n\n"
        "Report overflowing trash bins and we'll send a truck!\n\n"
        "Use the menu below 👇",
        parse_mode="HTML", reply_markup=main_menu(),
    )

async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 <b>Step 1 of 3</b> — Send a photo of the trash bin:",
        parse_mode="HTML",
    )
    return WAITING_PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo_id"] = update.message.photo[-1].file_id
    await update.message.reply_text(
        "✅ Photo received!\n\n📍 <b>Step 2 of 3</b> — Share your location:",
        parse_mode="HTML", reply_markup=location_keyboard(),
    )
    return WAITING_LOCATION

async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    context.user_data["lat"] = loc.latitude
    context.user_data["lon"] = loc.longitude
    await update.message.reply_text(
        "✅ Location saved!\n\n💬 <b>Step 3 of 3</b> — Add a note or tap Skip:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([["➡️ Skip"]], resize_keyboard=True),
    )
    return WAITING_DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    desc = None if text == "➡️ Skip" else text
    user = update.effective_user
    d = context.user_data
    report_id = db.create_report(
        user_id=user.id, full_name=user.full_name, username=user.username,
        photo_id=d["photo_id"], lat=d["lat"], lon=d["lon"], description=desc,
    )
    report = db.get_report(report_id)
    await update.message.reply_text(
        f"🎉 <b>Report submitted!</b>\n\n"
        f"🆔 Report ID: <code>#{report_id}</code>\n"
        f"⏳ Status: Under Review\n\n"
        "Thank you! 🌱",
        parse_mode="HTML", reply_markup=main_menu(),
    )
    await notify_admins(context, report)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu())
    return ConversationHandler.END

async def my_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reports = db.get_user_reports(update.effective_user.id)
    if not reports:
        await update.message.reply_text("📭 No reports yet.", reply_markup=main_menu())
        return
    lines = ["📋 <b>Your Reports</b>\n"]
    for r in reports:
        lines.append(f"🔹 <b>#{r['id']}</b> {STATUS_TEXT.get(r['status'], r['status'])}\n   📅 {r['created_at'][:16]}\n")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=main_menu())

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ <b>How it works:</b>\n\n"
        "1️⃣ Tap «📸 Report a Trash Bin»\n"
        "2️⃣ Send a photo\n"
        "3️⃣ Share your location\n"
        "4️⃣ Add a note (optional)\n"
        "5️⃣ Done — truck will be sent!\n\n"
        "⏳ Under Review\n✅ Approved\n🏁 Completed\n❌ Rejected",
        parse_mode="HTML", reply_markup=main_menu(),
    )

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No permission.")
        return
    s = db.get_stats()
    await update.message.reply_text(
        f"🛠 <b>Admin Panel</b>\n\n"
        f"👥 Users: {s['users']}\n📋 Total: {s['total']}\n"
        f"⏳ Pending: {s['pending']}\n✅ Approved: {s['approved']}\n🏁 Done: {s['completed']}\n\n"
        "/pending — pending reports",
        parse_mode="HTML",
    )

async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    reports = db.get_all_reports(status="pending")
    if not reports:
        await update.message.reply_text("✅ No pending reports.")
        return
    for r in reports[:5]:
        maps = f"https://maps.google.com/?q={r['lat']},{r['lon']}"
        await update.message.reply_photo(
            photo=r["photo_id"],
            caption=f"🆔 #{r['id']} | 👤 {r['full_name']}\n📍 <a href='{maps}'>Map</a>\n💬 {r.get('description') or '—'}",
            parse_mode="HTML", reply_markup=admin_buttons(r["id"]),
        )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ No permission.", show_alert=True)
        return
    action, rid = query.data.split("_", 1)
    rid = int(rid)
    report = db.get_report(rid)
    if not report:
        return
    name = query.from_user.full_name
    old = query.message.caption or ""

    msgs = {
        "approve": f"🚛 Report <code>#{rid}</code> approved! Truck is on the way. ETA: 2–4 hours ⏱",
        "reject":  f"ℹ️ Report <code>#{rid}</code> was not approved. Please resubmit with a clearer photo.",
        "complete":f"🏁 Report <code>#{rid}</code> completed! Trash collected. Thank you! 🌱",
    }
    statuses = {"approve": "approved", "reject": "rejected", "complete": "completed"}
    labels   = {"approve": "✅ APPROVED", "reject": "❌ REJECTED", "complete": "🏁 COMPLETED"}

    if action in statuses:
        db.update_report_status(rid, statuses[action])
        try:
            await context.bot.send_message(chat_id=report["user_id"], text=msgs[action], parse_mode="HTML")
        except Exception as e:
            logger.warning("User notify error: %s", e)
        await query.edit_message_caption(old + f"\n\n{labels[action]} by {name}", parse_mode="HTML")
    elif action == "seen":
        await query.edit_message_caption(old + f"\n\n👁 Seen by {name}", parse_mode="HTML")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📸 Report a Trash Bin$"), report_start)],
        states={
            WAITING_PHOTO:       [MessageHandler(filters.PHOTO, receive_photo)],
            WAITING_LOCATION:    [MessageHandler(filters.LOCATION, receive_location), MessageHandler(filters.Regex("^❌ Cancel$"), cancel_report)],
            WAITING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel_report)],
    )
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("admin",   cmd_admin))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^📋 My Reports$"), my_reports))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"),       cmd_help))
    app.add_handler(CallbackQueryHandler(admin_callback))
    logger.info("CleanCity Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
