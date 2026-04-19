"""
╔══════════════════════════════════════════════════════════════╗
║        🎬 VIDEO DOWNLOADER BOT — Single File Version        ║
║   TikTok | Instagram | Facebook — by @shuvo_bhai11          ║
╚══════════════════════════════════════════════════════════════╝

▶ Install:  pip install python-telegram-bot aiohttp
▶ Run:      python video_bot.py
"""

import logging
import asyncio
import aiohttp
import sqlite3
import re
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMember, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ═══════════════════════════════════════════════════════════════
#   ⚙️  কনফিগারেশন
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN    = "8615892662:AAErSwS0emGu1fpXji11_5EnaovfUPclBes"
ADMIN_IDS    = [7596820363]

CHANNEL_1_ID   = "@shuvofiles"
CHANNEL_1_LINK = "https://t.me/shuvofiles"

CHANNEL_2_ID   = "@shuvo_bhai11"
CHANNEL_2_LINK = "https://t.me/shuvo_bhai11"

DATABASE_FILE    = "bot_data.db"
REQUEST_TIMEOUT  = 30

# ═══════════════════════════════════════════════════════════════
#   🗄️  ডেটাবেস
# ═══════════════════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT    DEFAULT '',
                first_name  TEXT    DEFAULT '',
                downloads   INTEGER DEFAULT 0,
                is_banned   INTEGER DEFAULT 0,
                joined_date TEXT    DEFAULT CURRENT_TIMESTAMP
            );
        """)

def db_add_user(user_id, username, first_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?,?,?,?)",
            (user_id, username or "", first_name or "", datetime.now().strftime("%Y-%m-%d %H:%M"))
        )

def db_get_user(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

def db_all_users():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM users WHERE is_banned=0 ORDER BY joined_date DESC"
        ).fetchall()]

def db_total_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def db_total_downloads():
    with get_conn() as conn:
        r = conn.execute("SELECT SUM(downloads) FROM users").fetchone()[0]
        return r or 0

def db_increment(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET downloads=downloads+1 WHERE user_id=?", (user_id,))

def db_ban(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))

def db_unban(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))

def db_is_banned(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["is_banned"])

# ═══════════════════════════════════════════════════════════════
#   📥  ডাউনলোডার
# ═══════════════════════════════════════════════════════════════

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

async def tiktok_info(url: str):
    """TikWM API — watermark-free TikTok download"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://www.tikwm.com/api/",
                params={"url": url, "hd": 1},
                headers={"User-Agent": BROWSER_UA},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as r:
                if r.status != 200:
                    return None
                d = await r.json()
                if d.get("code") != 0:
                    return None
                v = d.get("data", {})
                return {
                    "video_url": v.get("hdplay") or v.get("play"),
                    "author":    v.get("author", {}).get("nickname", "অজানা"),
                    "title":     v.get("title", ""),
                    "likes":     v.get("digg_count", 0),
                    "comments":  v.get("comment_count", 0),
                }
    except Exception as e:
        logging.error(f"TikTok error: {e}")
        return None

async def instagram_info(url: str):
    """SnapInsta API — Instagram Reels/Video download"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://snapinsta.app/action.php",
                data={"url": url, "lang": "en"},
                headers={
                    "User-Agent": BROWSER_UA,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://snapinsta.app/",
                    "Origin":  "https://snapinsta.app",
                },
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json(content_type=None)
                # Extract first video link from response
                if isinstance(data, dict):
                    links = data.get("links", [])
                    if links:
                        return {"video_url": links[0].get("url") or links[0].get("link")}
                    # Some versions return url directly
                    url_val = data.get("url") or data.get("video")
                    if url_val:
                        return {"video_url": url_val}
                return None
    except Exception as e:
        logging.error(f"Instagram error: {e}")
        return None

async def facebook_info(url: str):
    """Getfvid API — Facebook HD/SD download"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://getfvid.com/api",
                data={"url": url},
                headers={
                    "User-Agent": BROWSER_UA,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://getfvid.com/",
                    "Origin":  "https://getfvid.com",
                },
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json(content_type=None)
                if isinstance(data, dict):
                    return {
                        "hd_url": data.get("hd") or data.get("hd_url"),
                        "sd_url": data.get("sd") or data.get("sd_url") or data.get("url"),
                    }
                return None
    except Exception as e:
        logging.error(f"Facebook error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
#   🔧  হেলপার ফাংশন
# ═══════════════════════════════════════════════════════════════

def detect_platform(url: str):
    u = url.lower()
    if "tiktok.com" in u or "vm.tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u or "instagr.am" in u:
        return "instagram"
    if "facebook.com" in u or "fb.com" in u or "fb.watch" in u:
        return "facebook"
    return None

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

async def check_membership(bot, user_id: int) -> bool:
    for ch in [CHANNEL_1_ID, CHANNEL_2_ID]:
        if not ch:
            continue
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in [ChatMember.LEFT, ChatMember.BANNED, "kicked"]:
                return False
        except Exception as e:
            logging.warning(f"Membership check failed {ch}: {e}")
            return False
    return True

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 চ্যানেল ১ জয়েন করুন", url=CHANNEL_1_LINK)],
        [InlineKeyboardButton("📢 চ্যানেল ২ জয়েন করুন", url=CHANNEL_2_LINK)],
        [InlineKeyboardButton("✅ জয়েন করেছি — চেক করুন", callback_data="check_join")],
    ])

# ═══════════════════════════════════════════════════════════════
#   💬  কমান্ড হ্যান্ডেলার
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_user(user.id, user.username, user.first_name)

    if not await check_membership(context.bot, user.id):
        await update.message.reply_text(
            f"👋 স্বাগতম <b>{user.first_name}</b>!\n\n"
            "🔒 বট ব্যবহার করতে নিচের <b>দুটি চ্যানেলে</b> জয়েন করুন,\n"
            "তারপর <b>«✅ জয়েন করেছি»</b> বাটনে ক্লিক করুন।",
            parse_mode=ParseMode.HTML,
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        "🎬 <b>ভিডিও ডাউনলোডার বট</b>\n\n"
        f"👋 স্বাগতম <b>{user.first_name}</b>!\n\n"
        "📌 <b>সাপোর্টেড প্ল্যাটফর্ম:</b>\n"
        "  🎵 TikTok — ওয়াটারমার্ক ছাড়া\n"
        "  📸 Instagram Reels ও ভিডিও\n"
        "  📘 Facebook ভিডিও (HD / SD)\n\n"
        "🔗 যেকোনো ভিডিওর <b>লিঙ্ক পেস্ট করুন</b>,\n"
        "আমি ডাউনলোড করে পাঠিয়ে দেব! ✅\n\n"
        "📊 /stats — আপনার তথ্য\n"
        "ℹ️ /help  — সাহায্য",
        parse_mode=ParseMode.HTML
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>কীভাবে ব্যবহার করবেন</b>\n\n"
        "১️⃣ TikTok / Instagram / Facebook ভিডিও ওপেন করুন\n"
        "২️⃣ ভিডিওর লিঙ্ক কপি করুন\n"
        "৩️⃣ এই বটে পেস্ট করে Send করুন\n"
        "৪️⃣ কয়েক সেকেন্ড অপেক্ষা করুন ✅\n\n"
        "🔗 <b>লিঙ্ক ফরম্যাট উদাহরণ:</b>\n"
        "• https://www.tiktok.com/@user/video/...\n"
        "• https://vm.tiktok.com/...\n"
        "• https://www.instagram.com/reel/...\n"
        "• https://www.facebook.com/watch?v=...\n"
        "• https://fb.watch/...\n\n"
        "⚠️ শুধু <b>পাবলিক</b> ভিডিও ডাউনলোড করা যায়।",
        parse_mode=ParseMode.HTML
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db_get_user(update.effective_user.id)
    if u:
        await update.message.reply_text(
            f"📊 <b>আপনার তথ্য</b>\n\n"
            f"👤 নাম: <b>{u['first_name']}</b>\n"
            f"🆔 ID: <code>{u['user_id']}</code>\n"
            f"📥 মোট ডাউনলোড: <b>{u['downloads']}</b>\n"
            f"📅 যোগদানের তারিখ: {u['joined_date']}",
            parse_mode=ParseMode.HTML
        )

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন।")
        return

    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 ব্রডকাস্ট", callback_data="adm_broadcast"),
         InlineKeyboardButton("📊 স্ট্যাটস",  callback_data="adm_stats")],
        [InlineKeyboardButton("👥 ইউজার লিস্ট", callback_data="adm_users")],
        [InlineKeyboardButton("🚫 ব্যান",       callback_data="adm_ban_info"),
         InlineKeyboardButton("✅ আনব্যান",     callback_data="adm_unban_info")],
    ])

    await update.message.reply_text(
        f"🛡 <b>এডমিন প্যানেল</b>\n\n"
        f"👥 মোট ইউজার: <b>{db_total_users()}</b>\n"
        f"📥 মোট ডাউনলোড: <b>{db_total_downloads()}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kbd
    )

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "📨 ব্রডকাস্ট:\n<code>/broadcast আপনার মেসেজ</code>",
            parse_mode=ParseMode.HTML
        )
        return

    msg_text = " ".join(context.args)
    users    = db_all_users()
    ok, fail = 0, 0

    info = await update.message.reply_text("📨 ব্রডকাস্ট শুরু হচ্ছে...")

    for u in users:
        try:
            await context.bot.send_message(
                u["user_id"],
                f"📢 <b>নোটিশ</b>\n\n{msg_text}",
                parse_mode=ParseMode.HTML
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1

    await info.edit_text(
        f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n"
        f"✅ সফল: {ok}\n❌ ব্যর্থ: {fail}\n📊 মোট: {ok+fail}",
        parse_mode=ParseMode.HTML
    )

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("ব্যবহার: <code>/ban user_id</code>", parse_mode=ParseMode.HTML)
        return
    try:
        uid = int(context.args[0])
        db_ban(uid)
        await update.message.reply_text(f"✅ ইউজার <code>{uid}</code> ব্যান হয়েছে।", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ সঠিক User ID দিন।")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("ব্যবহার: <code>/unban user_id</code>", parse_mode=ParseMode.HTML)
        return
    try:
        uid = int(context.args[0])
        db_unban(uid)
        await update.message.reply_text(f"✅ ইউজার <code>{uid}</code> আনব্যান হয়েছে।", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ সঠিক User ID দিন।")

async def cmd_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        f"👥 মোট ইউজার: <b>{db_total_users()}</b>",
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════════════════════
#   🔘  কলব্যাক হ্যান্ডেলার
# ═══════════════════════════════════════════════════════════════

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    user = q.from_user

    # ── চ্যানেল চেক ──
    if data == "check_join":
        if await check_membership(context.bot, user.id):
            await q.message.edit_text(
                "✅ <b>ধন্যবাদ!</b> এখন যেকোনো ভিডিওর লিঙ্ক পাঠান!",
                parse_mode=ParseMode.HTML
            )
        else:
            await q.message.edit_text(
                "❌ এখনও সব চ্যানেলে জয়েন করেননি।\nজয়েন করুন তারপর আবার চেক করুন।",
                parse_mode=ParseMode.HTML,
                reply_markup=join_keyboard()
            )
        return

    # ── এডমিন কলব্যাক ──
    if not is_admin(user.id):
        return

    if data == "adm_stats":
        await q.message.reply_text(
            f"📊 <b>বটের পরিসংখ্যান</b>\n\n"
            f"👥 মোট ইউজার: <b>{db_total_users()}</b>\n"
            f"📥 মোট ডাউনলোড: <b>{db_total_downloads()}</b>",
            parse_mode=ParseMode.HTML
        )

    elif data == "adm_broadcast":
        await q.message.reply_text(
            "📨 ব্রডকাস্ট করতে:\n<code>/broadcast আপনার মেসেজ</code>",
            parse_mode=ParseMode.HTML
        )

    elif data == "adm_users":
        rows = db_all_users()[:15]
        txt  = "👥 <b>সর্বশেষ ১৫ জন ইউজার:</b>\n\n"
        for u in rows:
            name = u["first_name"] or "নামহীন"
            txt += f"• {name} | <code>{u['user_id']}</code> | ⬇️{u['downloads']}\n"
        await q.message.reply_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_ban_info":
        await q.message.reply_text(
            "ব্যান করতে:\n<code>/ban user_id</code>",
            parse_mode=ParseMode.HTML
        )

    elif data == "adm_unban_info":
        await q.message.reply_text(
            "আনব্যান করতে:\n<code>/unban user_id</code>",
            parse_mode=ParseMode.HTML
        )

    # ── Facebook কোয়ালিটি সিলেকশন ──
    elif data.startswith("fb_hd:") or data.startswith("fb_sd:"):
        quality, video_url = data.split(":", 1)
        quality_label = "HD 🎬" if quality == "fb_hd" else "SD 📱"
        loading = await q.message.reply_text(f"📥 Facebook {quality_label} পাঠানো হচ্ছে...")
        await q.message.delete()
        caption = (
            f"📘 <b>Facebook ভিডিও ({quality_label})</b>\n\n"
            f"🤖 @{context.bot.username}"
        )
        try:
            await loading.reply_video(video=video_url, caption=caption, parse_mode=ParseMode.HTML, supports_streaming=True)
            db_increment(user.id)
            await loading.delete()
        except Exception:
            await loading.edit_text(
                f"✅ <b>Facebook ভিডিও লিঙ্ক ({quality_label}):</b>\n"
                f"<a href='{video_url}'>এখানে ক্লিক করুন</a>",
                parse_mode=ParseMode.HTML
            )
            db_increment(user.id)

# ═══════════════════════════════════════════════════════════════
#   📨  মেসেজ হ্যান্ডেলার (লিঙ্ক প্রসেস)
# ═══════════════════════════════════════════════════════════════

URL_RE = re.compile(r'https?://\S+')

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()

    if db_is_banned(user.id):
        await update.message.reply_text("❌ আপনি এই বট ব্যবহার করতে পারবেন না।")
        return

    if not await check_membership(context.bot, user.id):
        await update.message.reply_text(
            "🔒 বট ব্যবহার করতে উভয় চ্যানেলে জয়েন করুন:",
            reply_markup=join_keyboard()
        )
        return

    urls = URL_RE.findall(text)
    if not urls:
        await update.message.reply_text(
            "🔗 একটি বৈধ ভিডিও লিঙ্ক পাঠান।\n"
            "✅ সাপোর্টেড: TikTok • Instagram • Facebook"
        )
        return

    url      = urls[0]
    platform = detect_platform(url)

    if not platform:
        await update.message.reply_text(
            "❌ এই লিঙ্কটি সাপোর্টেড নয়।\n"
            "✅ TikTok, Instagram বা Facebook লিঙ্ক পাঠান।"
        )
        return

    icons = {"tiktok": "🎵 TikTok", "instagram": "📸 Instagram", "facebook": "📘 Facebook"}
    wait  = await update.message.reply_text(f"⏳ {icons[platform]} ভিডিও প্রসেস হচ্ছে...")

    try:
        if platform == "tiktok":
            await process_tiktok(update, context, url, wait, user.id)
        elif platform == "instagram":
            await process_instagram(update, context, url, wait, user.id)
        elif platform == "facebook":
            await process_facebook(update, context, url, wait, user.id)
    except Exception as e:
        logging.error(f"Process error [{platform}]: {e}")
        await wait.edit_text(
            "❌ ভিডিও ডাউনলোড করতে সমস্যা হয়েছে।\n"
            "ভিডিওটি পাবলিক কিনা চেক করুন এবং আবার চেষ্টা করুন।"
        )

# ─── প্ল্যাটফর্ম প্রসেসর ────────────────────────────────────

async def process_tiktok(update, context, url, wait_msg, user_id):
    res = await tiktok_info(url)
    if not res or not res.get("video_url"):
        await wait_msg.edit_text("❌ TikTok ভিডিও পাওয়া যায়নি। লিঙ্কটি সঠিক কিনা চেক করুন।")
        return

    await wait_msg.edit_text("📥 TikTok ভিডিও পাঠানো হচ্ছে...")
    caption = (
        f"🎵 <b>TikTok ভিডিও</b>\n"
        f"👤 {res.get('author','অজানা')}\n"
        f"❤️ {res.get('likes',0):,}  💬 {res.get('comments',0):,}\n\n"
        f"🤖 @{context.bot.username}"
    )
    try:
        await update.message.reply_video(
            video=res["video_url"], caption=caption,
            parse_mode=ParseMode.HTML, supports_streaming=True
        )
        db_increment(user_id)
        await wait_msg.delete()
    except Exception:
        await wait_msg.edit_text(
            f"✅ <b>TikTok ভিডিও লিঙ্ক (ওয়াটারমার্ক ছাড়া):</b>\n"
            f"<a href='{res['video_url']}'>ডাউনলোড করুন ⬇️</a>",
            parse_mode=ParseMode.HTML
        )
        db_increment(user_id)

async def process_instagram(update, context, url, wait_msg, user_id):
    res = await instagram_info(url)
    if not res or not res.get("video_url"):
        await wait_msg.edit_text("❌ Instagram ভিডিও পাওয়া যায়নি।\nপাবলিক পোস্টের লিঙ্ক দিন।")
        return

    await wait_msg.edit_text("📥 Instagram ভিডিও পাঠানো হচ্ছে...")
    caption = (
        f"📸 <b>Instagram ভিডিও</b>\n\n"
        f"🤖 @{context.bot.username}"
    )
    try:
        await update.message.reply_video(
            video=res["video_url"], caption=caption,
            parse_mode=ParseMode.HTML, supports_streaming=True
        )
        db_increment(user_id)
        await wait_msg.delete()
    except Exception:
        await wait_msg.edit_text(
            f"✅ <b>Instagram ভিডিও লিঙ্ক:</b>\n"
            f"<a href='{res['video_url']}'>ডাউনলোড করুন ⬇️</a>",
            parse_mode=ParseMode.HTML
        )
        db_increment(user_id)

async def process_facebook(update, context, url, wait_msg, user_id):
    res = await facebook_info(url)
    if not res or (not res.get("hd_url") and not res.get("sd_url")):
        await wait_msg.edit_text("❌ Facebook ভিডিও পাওয়া যায়নি।\nপাবলিক ভিডিওর লিঙ্ক দিন।")
        return

    hd = res.get("hd_url")
    sd = res.get("sd_url")

    if hd and sd:
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🎬 HD কোয়ালিটি", callback_data=f"fb_hd:{hd}")],
            [InlineKeyboardButton(f"📱 SD কোয়ালিটি", callback_data=f"fb_sd:{sd}")],
        ])
        await wait_msg.edit_text(
            "✅ <b>Facebook ভিডিও পাওয়া গেছে!</b>\n\nকোয়ালিটি বেছে নিন:",
            parse_mode=ParseMode.HTML,
            reply_markup=kbd
        )
    else:
        video_url = hd or sd
        caption   = f"📘 <b>Facebook ভিডিও</b>\n\n🤖 @{context.bot.username}"
        await wait_msg.edit_text("📥 Facebook ভিডিও পাঠানো হচ্ছে...")
        try:
            await update.message.reply_video(
                video=video_url, caption=caption,
                parse_mode=ParseMode.HTML, supports_streaming=True
            )
            db_increment(user_id)
            await wait_msg.delete()
        except Exception:
            await wait_msg.edit_text(
                f"✅ <b>Facebook ভিডিও লিঙ্ক:</b>\n"
                f"<a href='{video_url}'>ডাউনলোড করুন ⬇️</a>",
                parse_mode=ParseMode.HTML
            )
            db_increment(user_id)

# ═══════════════════════════════════════════════════════════════
#   🚀  মেইন
# ═══════════════════════════════════════════════════════════════

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start",     "বট শুরু করুন"),
        BotCommand("help",      "সাহায্য"),
        BotCommand("stats",     "আপনার তথ্য"),
        BotCommand("admin",     "এডমিন প্যানেল"),
        BotCommand("broadcast", "ব্রডকাস্ট (এডমিন)"),
        BotCommand("ban",       "ব্যান ইউজার (এডমিন)"),
        BotCommand("unban",     "আনব্যান ইউজার (এডমিন)"),
        BotCommand("total",     "মোট ইউজার (এডমিন)"),
    ])
    logging.info("✅ Bot commands set.")

def main():
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO
    )

    # Initialize database
    init_db()
    logging.info("✅ Database ready.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Register handlers
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("ban",       cmd_ban))
    app.add_handler(CommandHandler("unban",     cmd_unban))
    app.add_handler(CommandHandler("total",     cmd_total))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logging.info("🤖 বট চালু হচ্ছে...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
