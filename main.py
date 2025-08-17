import os
import time
import json
import requests
from bs4 import BeautifulSoup
import re
import threading
from datetime import datetime
from flask import Flask, request

# ----- CONFIG: read from ENV first, fallback to config.json if present -----
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_USER_ID")

# optional fallback to local config.json (only for local testing, DON'T commit real tokens)
if not BOT_TOKEN or not CHAT_ID:
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
            BOT_TOKEN = BOT_TOKEN or cfg.get("telegram_token")
            CHAT_ID   = CHAT_ID   or cfg.get("telegram_user_id") or cfg.get("chat_id")
    except Exception:
        pass

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def root():
    return "✅ Myntra Glitch Bot is up", 200

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/test-alert", methods=["GET"])
def test_alert():
    msg = request.args.get("msg", "Test alert from Myntra Glitch Bot ✅")
    send_telegram(msg)
    return "Sent", 200

# ----- Scan config -----
CATEGORY_URLS = [
    "https://www.myntra.com/men-clothing",
    "https://www.myntra.com/women-clothing",
    "https://www.myntra.com/men-shoes",
    "https://www.myntra.com/women-footwear",
    "https://www.myntra.com/watches",
    "https://www.myntra.com/home-living"
]

# final premium list you asked (updated)
PREMIUM_BRANDS = [
    "zara","nike","puma","mango","armani","tommy","ck","guess","h&m",
    "rare rabbit","jack & jones","pepe","lee","louis vuitton","levis","adidas",
    "asics","new balance","gap","snitch","mango man","gant","next","ether",
    "mr bowerbird","adidas original","jordan","puma motosports","the bear house",
    "linen","wrogn","bnana club","almaty","aldeno","locasto","pure cotton","locaste"
]

# normalize set (lowercase) for matching
PREMIUM_TERMS = set(p.lower() for p in PREMIUM_BRANDS)

SPECIAL_KEYWORDS = ["coupon", "extra off", "promo code", "coupon code", "discount code", "flat off"]

# thresholds
GENERAL_GLITCH_PERCENT = 80
GENERAL_GLITCH_AMOUNT  = 1000

PREMIUM_PERCENT = 50        # other premium brands
PREMIUM_AMOUNT  = 500

SPECIAL_BRAND_PERCENT = 40  # for nike/jordan
SPECIAL_BRAND_AMOUNT  = 500

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# de-dup set
SEEN = set()
MAX_SEEN = 1000

# daily ping tracker
_last_daily_date = None

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing. Set BOT_TOKEN and CHAT_ID in Render env.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def extract_prices_and_names(li):
    # Try class-based extraction first (Myntra typical structure)
    brand = None
    name = None
    price = None
    mrp = None

    try:
        b = li.find("h3", class_="product-brand") or li.find("h4", class_="product-brand")
        n = li.find("h4", class_="product-product") or li.find("h4")
        p_disc = li.find("span", class_="product-discountedPrice") or li.find("span", class_="discountedPriceText")
        p_mrp  = li.find("span", class_="product-strike") or li.find("span", class_="strike")
        if b: brand = b.get_text(strip=True)
        if n: name = n.get_text(strip=True)
        if p_disc: 
            price = parse_price(p_disc.get_text())
        if p_mrp:
            mrp = parse_price(p_mrp.get_text())
    except Exception:
        pass

    # fallback: regex on text
    text_all = li.get_text(" ", strip=True)
    if not brand or not name:
        # sometimes brand & name appear in text; we'll keep them low-confidence
        parts = text_all.split("\n")
        if not brand and len(parts) > 0:
            brand = (parts[0].strip() or brand)
        if not name and len(parts) > 1:
            name = (parts[1].strip() or name)

    if (price is None or mrp is None):
        # fallback: find ₹... numbers
        nums = re.findall(r"₹\s*([0-9,]+)", text_all)
        if nums:
            # heuristics: last is price, previous is mrp
            try:
                nums_clean = [int(n.replace(",", "")) for n in nums]
                if len(nums_clean) == 1:
                    price = price or nums_clean[0]
                else:
                    # assign last as price, first as mrp
                    price = price or nums_clean[-1]
                    mrp   = mrp   or nums_clean[0]
            except:
                pass

    return (brand or "").strip(), (name or "").strip(), price, mrp, text_all.lower()

def parse_price(s):
    try:
        s = s.replace("Rs.", "").replace("₹", "").replace(",", "").strip()
        return int(re.sub(r"[^\d]", "", s))
    except:
        return None

def is_premium_text(text_lower):
    for term in PREMIUM_TERMS:
        if term in text_lower:
            return True
    return False

def contains_special_keyword(text_lower):
    for k in SPECIAL_KEYWORDS:
        if k in text_lower:
            return True
    return False

def scan_category(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ {url} returned {r.status_code}")
            return 0
    except Exception as e:
        print("Request failed:", e)
        return 0

    soup = BeautifulSoup(r.text, "lxml")
    items = soup.find_all("li", class_="product-base")
    if not items:
        items = soup.find_all("li")

    alerts = 0
    for li in items:
        try:
            brand, name, price, mrp, text_lower = extract_prices_and_names(li)
            if not brand and not name and not price:
                continue

            # compute discount
            discount_amt = 0
            discount_per = 0
            if price and mrp and mrp > price:
                discount_amt = mrp - price
                discount_per = round((discount_amt / mrp) * 100)

            # conditions
            is_general_glitch = (discount_per >= GENERAL_GLITCH_PERCENT) or (discount_amt >= GENERAL_GLITCH_AMOUNT)
            is_premium = is_premium_text(text_lower)
            is_special_brand = any(s in text_lower for s in ["nike", "jordan"])
            has_coupon_keyword = contains_special_keyword(text_lower)

            notify = False
            reason = ""

            if is_general_glitch:
                notify = True
                reason = f"General glitch {discount_per}% / ₹{discount_amt}"
            elif is_special_brand and (discount_per >= SPECIAL_BRAND_PERCENT or discount_amt >= SPECIAL_BRAND_AMOUNT):
                notify = True
                reason = f"Special brand ({'nike/jordan'}) {discount_per}% / ₹{discount_amt}"
            elif is_premium and (discount_per >= PREMIUM_PERCENT or discount_amt >= PREMIUM_AMOUNT):
                notify = True
                reason = f"Premium {discount_per}% / ₹{discount_amt}"
            elif has_coupon_keyword and (is_premium or discount_amt >= PREMIUM_AMOUNT):
                notify = True
                reason = "Coupon / promo found"

            if notify:
                key = f"{brand}|{name}|{price}|{mrp}"
                if key in SEEN:
                    continue
                SEEN.add(key)
                # trim SEEN
                if len(SEEN) > MAX_SEEN:
                    # naive trim
                    for _ in range(len(SEEN) - MAX_SEEN):
                        SEEN.pop()

                link = ""
                a = li.find("a", href=True)
                if a:
                    href = a["href"]
                    if href.startswith("/"):
                        link = "https://www.myntra.com" + href
                    else:
                        link = href
                else:
                    link = url

                title = brand or "Unknown brand"
                pname = name or "Product"
                message = (
                    f"🧨 <b>Loot Alert</b>\n"
                    f"🧾 <b>{title}</b> — {pname}\n"
                    f"💸 Price: ₹{price if price else 'N/A'} (MRP: ₹{mrp if mrp else 'N/A'})\n"
                    f"📉 Discount: {discount_per}%  (₹{discount_amt})\n"
                    f"🔎 Reason: {reason}\n"
                    f"🔗 {link}"
                )
                send_telegram(message)
                alerts += 1

        except Exception as e:
            continue

    print(f"✅ Scanned {url}  — alerts: {alerts}")
    return alerts

def daily_ping_once():
    global _last_daily_date
    today = datetime.now().date()
    if _last_daily_date != today:
        send_telegram("📢 Daily Ping: Myntra Glitch Bot is LIVE & Running!")
        _last_daily_date = today

def loop_scan():
    print("🚀 Scanner thread started")
    while True:
        try:
            daily_ping_once()
            for url in CATEGORY_URLS:
                scan_category(url)
            # random sleep to avoid predictable scraping pattern
            time.sleep(30 + int(time.time()) % 31)
        except Exception as e:
            print("Scanner error:", e)
            time.sleep(60)

# start scanner in background when module imported (gunicorn will import module)
threading.Thread(target=loop_scan, daemon=True).start()

# run Flask only if executed directly (for local dev)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
