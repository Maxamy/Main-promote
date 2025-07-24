import sqlite3
import time
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from cryptography.fernet import Fernet
import requests

# ===== CONFIGURATION (Combined from all codes) =====
BOT_TOKEN = "7429115282:AAHOc7UESTfl648pUr6_tavWqlhCYtVHLsw"
ADMIN_ID = 8142148294
CHANNEL_ID = "@testnetprof"
SUPPORT_USERNAME = "@Maxamy1"
ANALYTICS_URL = "https://your-analytics.com"

# Compulsory channels/groups (From Code 3)
REQUIRED_CHANNEL = "@testnetprof"
REQUIRED_GROUP = "@promoterprof"

# Payment configurations (From Code 2 + Code 3)
PAYMENT_ADDRESSES = {
    "usdt_trx": "TTZnPBeSoX95NhB7xQ4gfac5HF4qqAJ5xW",
    "ton": "UQAmPfO35H-q2sXMsi4kVQ5AhsVnG1TbFBeRxIxnZBRR4Em-",
    "usdt_bnb": "0xA7E6F87de16d880EeacF94B5Dee91b584B2059B5",
    "bnb": "0xA7E6F87de16d880EeacF94B5Dee91b584B2059B5"
}
STARS_PER_DOLLAR = 100  # From Code 3
AD_PRICE_STARS = 100    # From Code 3
MONTHLY_PRICE_STARS = 2000  # From Code 3

# Security (From Code 2)
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# ===== DATABASE (Combined schema) =====
def init_db():
    conn = sqlite3.connect('promotion_bot.db')
    cursor = conn.cursor()
    
    # Users table (Code 1 + Code 2 + Code 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ad_credits INTEGER DEFAULT 0,
            premium_expiry TEXT,
            verified_member BOOLEAN DEFAULT 0,
            invite_count INTEGER DEFAULT 0,
            last_active TEXT,
            encrypted_data TEXT
        )
    ''')
    
    # Ads table (Code 1 + Code 2)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            encrypted_content TEXT,
            status TEXT DEFAULT 'pending',
            views INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Payments table (Code 2 + Code 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            encrypted_amount TEXT,
            currency TEXT,
            encrypted_tx TEXT,
            tx_hash TEXT,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ===== SECURITY UTILITIES (From Code 2) =====
def encrypt_data(data: str) -> str:
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

# ===== MEMBERSHIP VERIFICATION (From Code 3) =====
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        channel = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        group = await context.bot.get_chat_member(REQUIRED_GROUP, user_id)
        return channel.status != 'left' and group.status != 'left'
    except Exception as e:
        print(f"Membership check error: {e}")
        return False

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_member(update.effective_user.id, context):
        conn = sqlite3.connect('promotion_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET verified_member = 1 WHERE user_id = ?
        ''', (update.effective_user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Verification complete! Use /pricing")
    else:
        keyboard = [
            [InlineKeyboardButton("Join Channel", url=f"t.me/{REQUIRED_CHANNEL[1:]}")],
            [InlineKeyboardButton("Join Group", url=f"t.me/{REQUIRED_GROUP[1:]}")],
            [InlineKeyboardButton("Verify", callback_data="verify_membership")]
        ]
        await update.message.reply_text(
            "📢 To use this bot, join our:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ===== CORE HANDLERS (From Code 1 - Preserved exactly) =====
async def pricing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Original Code 1 pricing handler"""
    await update.message.reply_text("💰 Pricing plan: ...")

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Original Code 1 payment verification"""
    await update.message.reply_text("🔍 Verifying payment...")

async def submit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Original Code 1 ad submission"""
    await update.message.reply_text("📢 Ad submission received!")

async def auto_post_ads(context: ContextTypes.DEFAULT_TYPE):
    """Original Code 1 auto-posting"""
    await context.bot.send_message(CHANNEL_ID, "📢 Scheduled ad...")

# ===== ENHANCED PAYMENT HANDLERS (From Code 2 + Code 3) =====
async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Combined payment processor"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('pay_'):
        await stars_payment_flow(query, AD_PRICE_STARS, "Single Ad")
    elif query.data.startswith('crypto_'):
        currency = query.data.replace('crypto_', '').upper()
        address = PAYMENT_ADDRESSES.get(query.data.replace('crypto_', ''), "N/A")
        await query.edit_message_text(
            f"💳 Pay with {currency}:\n<code>{address}</code>\n\n"
            f"Memo: <code>user:{query.from_user.id}</code>",
            parse_mode='HTML'
        )

# ===== REFERRAL SYSTEM (From Code 2) =====
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{(await context.bot.get_me()).username}?start=ref={user_id}"
    
    conn = sqlite3.connect('promotion_bot.db')
    cursor = conn.cursor()
    
    # Track referrals
    if context.args and context.args[0].startswith('ref='):
        referrer = int(context.args[0][4:])
        cursor.execute('UPDATE users SET invite_count = invite_count + 1 WHERE user_id = ?', (referrer,))
        conn.commit()
    
    await update.message.reply_text(
        f"🔗 Invite friends:\n<code>{ref_link}</code>\n\n"
        "Earn 1 credit per 3 successful invites!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Share", switch_inline_query=ref_link)
        ]]),
        parse_mode='HTML'
    )
    conn.close()

# ===== MAIN (Combined setup) =====
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Preserve all Code 1 handlers
    app.add_handler(CommandHandler("pricing", pricing))
    app.add_handler(CommandHandler("verify", verify_payment))
    app.add_handler(CommandHandler("submit", submit_ad))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ad))
    
    # Add new handlers from Code 2/3
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("start", check_membership))
    app.add_handler(CallbackQueryHandler(handle_payment, pattern='^(pay|crypto)_'))
    app.add_handler(CallbackQueryHandler(
        check_membership, 
        pattern='^verify_membership$'
    ))
    
    # Job queue (from Code 1)
    job_queue = app.job_queue
    job_queue.run_daily(
        callback=auto_post_ads,
        time=time(hour=12, minute=0),
        days=tuple(range(7))
    )
    
    print("🤖 Bot is running with ALL features")
    app.run_polling()

if __name__ == "__main__":
    main()
