import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types
import requests

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
MAILSLURP_API_KEY = os.environ.get("MAILSLURP_API_KEY", "sk_vsNq5tN0Dwci03II_FffmvLhXGoa6q5sjVIol6OwNSZJNpmvN0bCWTZHTBIXrOKLFm6rHBYHnWsaWYA5d")
BASE = "https://api.mailslurp.com"
HEADERS = {"x-api-key": MAILSLURP_API_KEY}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
USER = {}

# ---------- WEB SERVER (For Render 24/7 ping) ----------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# ---------- MAILSLURP HELPERS ----------
def create_inbox():
    try:
        r = requests.post(f"{BASE}/inboxes", headers=HEADERS, timeout=20)
        if r.status_code in (200, 201):
            d = r.json()
            return d.get("id"), d.get("emailAddress")
    except: pass
    return None, None

def get_emails(inbox_id):
    try:
        r = requests.get(f"{BASE}/inboxes/{inbox_id}/emails?size=10&sort=DESC", headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json() or []
    except: pass
    return []

def get_email(inbox_id, email_id):
    try:
        r = requests.get(f"{BASE}/inboxes/{inbox_id}/emails/{email_id}", headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json()
    except: pass
    return None

def extract_otp(text):
    if not text: return None
    for p in [r"(?:code|otp|pin|verification)[^\d]{0,15}(\d{4,8})", r"\b(\d{6})\b", r"\b(\d{4,8})\b"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: return m.group(1)
    return None

# ---------- /start ----------
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    text = (
        "👑 <b>PREMIUM TEMP MAIL</b>\n\n"
        "📧 Generate Unlimited Temporary Emails\n"
        "📥 Receive Real Emails & OTP Codes\n"
        "⚡ Fast • Secure • Professional\n\n"
        "👨‍💻 <b>Developer:</b> @ZAMINTHELEGEND"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📢 Join Official Channel", url="https://t.me/KINGPROFESSORBACK"),
        types.InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/ZAMINTHELEGEND"),
        types.InlineKeyboardButton("🚀 Generate Email", callback_data="gen"),
    )
    bot.send_message(msg.chat.id, text, reply_markup=kb)

# ---------- CALLBACKS ----------
@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        uid = call.from_user.id
        cid = call.message.chat.id
        mid = call.message.message_id
        data = call.data

        if data == "gen":
            bot.answer_callback_query(call.id, "⏳ Creating...")
            inbox_id, address = create_inbox()
            if not inbox_id:
                bot.answer_callback_query(call.id, "❌ API Error", show_alert=True)
                return
            USER[uid] = {"id": inbox_id, "address": address, "cache": []}
            
            text = f"✅ <b>New Email</b>\n\n📧 <code>{address}</code>"
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
                types.InlineKeyboardButton("📥 Read", callback_data="read")
            )
            kb.add(types.InlineKeyboardButton("🗑 Delete", callback_data="del"))
            bot.edit_message_text(text, cid, mid, reply_markup=kb)

        elif data in ["refresh", "read"]:
            info = USER.get(uid)
            if not info:
                bot.answer_callback_query(call.id, "❌ Generate email first!", show_alert=True)
                return
            emails = get_emails(info["id"])
            info["cache"] = emails
            if not emails:
                text = f"📭 <b>Inbox Empty</b>\n\n📮 <code>{info['address']}</code>"
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh"))
                bot.edit_message_text(text, cid, mid, reply_markup=kb)
            else:
                text = f"📥 <b>{len(emails)} Emails</b>\n\nSelect one:"
                kb = types.InlineKeyboardMarkup(row_width=1)
                for i, em in enumerate(emails[:8]):
                    subj = (em.get("subject") or "No Subject")[:30]
                    kb.add(types.InlineKeyboardButton(f"📩 {subj}", callback_data=f"view_{i}"))
                kb.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh"))
                bot.edit_message_text(text, cid, mid, reply_markup=kb)

        elif data.startswith("view_"):
            idx = int(data.split("_")[1])
            info = USER.get(uid)
            if info and idx < len(info["cache"]):
                em = info["cache"][idx]
                full = get_email(info["id"], em.get("id")) or em
                body = full.get("body") or ""
                otp = extract_otp(body + " " + (full.get("subject") or ""))
                
                text = f"📩 <b>{full.get('subject', 'No Subject')}</b>\n\n<pre>{body[:800]}</pre>"
                kb = types.InlineKeyboardMarkup()
                if otp:
                    text += f"\n\n🔑 <b>OTP:</b> <code>{otp}</code>"
                kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="read"))
                bot.edit_message_text(text, cid, mid, reply_markup=kb)

        elif data == "del":
            if uid in USER: del USER[uid]
            bot.edit_message_text("🗑 <b>Inbox Deleted</b>\n\nTap /start to begin.", cid, mid)

    except Exception as e:
        print(e)

# ---------- RUN ----------
if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    print("Bot is running...")
    bot.infinity_polling()
