import os
import time
import json
import requests
from bs4 import BeautifulSoup
import re
import threading
from datetime import datetime
from flask import Flask, request

# ----- CONFIG -----
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_USER_ID")

# Optional: comma-separated product URLs env
ENV_PRODUCT_URLS = [u.strip() for u in (os.getenv("PRODUCT_URLS") or "").split(",") if u.strip()]

# Fallback from config.json
CONFIG_PRODUCT_URLS = []
if not BOT_TOKEN or not CHAT_ID or not ENV_PRODUCT_URLS:
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
            BOT_TOKEN = BOT_TOKEN or cfg.get("telegram_token")
            CHAT_ID   = CHAT_ID   or cfg.get("telegram_user_id") or cfg.get("chat_id")
            CONFIG_PRODUCT_URLS = cfg.get("product_urls", [])
    except Exception:
        pass

# Final product URLs list (categories ke saath-saath inko bhi poll karenge)
PRODUCT_URLS = [u for u in (ENV_PRODUCT_URLS or CONFIG_PRODUCT_URLS) if isinstance(u, str) and u.strip()]
# Example: yahan add kar sakta hai agar env/config se set nahi karna
# PRODUCT_URLS.append("https://www.myntra.com/mailers/shoes/nike/nike-men's-v5-rnr-sneakers/34951432/buy?utm_source=social_share_pdp&utm_medium=deeplink&utm_campaign=social_share_pdp_deeplink")

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

PREMIUM_BRANDS = [
    "zara","nike","puma","mango","armani","tommy","ck","guess","h&m",
    "rare rabbit","jack & jones","pepe","lee","louis vuitton","levis","adidas",
    "asics","new balance","gap","snitch","mango man","gant","next","ether",
    "mr bowerbird","adidas original","jordan","puma motosports","the bear house",
    "linen","wrogn","bnana club","almaty","aldeno","locasto","pure cotton","locaste","only"
]

PREMIUM_TERMS = set(p.lower() for p in PREMIUM_BRANDS)
SPECIAL_KEYWORDS = ["coupon", "extra off", "promo code", "coupon code", "discount code", "flat off"]

GENERAL_GLITCH_PERCENT = 80
GENERAL_GLITCH_AMOUNT  = 1000
PREMIUM_PERCENT = 50
PREMIUM_AMOUNT  = 500
SPECIAL_BRAND_PERCENT = 40
SPECIAL_BRAND_AMOUNT  = 500

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

SEEN = set()
MAX_SEEN = 1000
_last_daily_date = None

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def parse_price(s):
    try:
        s = s.replace("Rs.", "").replace("₹", "").replace(",", "").strip()
        return int(re.sub(r"[^\d]", "", s))
    except:
        return None

def extract_prices_and_names(li):
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
        if p_disc: price = parse_price(p_disc.get_text())
        if p_mrp: mrp = parse_price(p_mrp.get_text())
    except:
        pass

    text_all = li.get_text(" ", strip=True)
    if not brand or not name:
        parts = text_all.split("\n")
        if not brand and len(parts) > 0: brand = (parts[0].strip() or brand)
        if not name and len(parts) > 1: name = (parts[1].strip() or name)

    if price is None or mrp is None:
        nums = re.findall(r"₹\s*([0-9,]+)", text_all)
        if nums:
            try:
                nums_clean = [int(n.replace(",", "")) for n in nums]
                if len(nums_clean) == 1:
                    price = price or nums_clean[0]
                else:
                    price = price or nums_clean[-1]
                    mrp   = mrp   or nums_clean[0]
            except:
                pass

    return (brand or "").strip(), (name or "").strip(), price, mrp, text_all.lower()

def is_premium_text(text_lower):
    return any(term in text_lower for term in PREMIUM_TERMS)

def contains_special_keyword(text_lower):
    return any(k in text_lower for k in SPECIAL_KEYWORDS)

def extract_coupon(text):
    if not text:
        return 0
    m = re.search(r"₹\s?(\d+)", str(text).replace(",", ""))
    return int(m.group(1)) if m else 0

def fetch_coupon_data(product_url):
    """Myntra product offers API (JS)"""
    try:
        product_id = re.search(r"/(\d+)(?:/|$|\?)", product_url)
        if not product_id:
            return False, ""
        pid = product_id.group(1)
        url = f"https://www.myntra.com/api/product/{pid}/offers"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and data.get("offers"):
                for offer in data["offers"]:
                    amt = int(offer.get("discount_amount", 0) or 0)
                    desc = offer.get("description", "") or ""
                    if amt >= 500 or extract_coupon(desc) >= 500:
                        return True, desc or f"₹{amt} off"
        return False, ""
    except:
        return False, ""

def fetch_coupon_html(product_url):
    """HTML parsing se coupon check karega (improved version)"""
    try:
        r = requests.get(product_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return False, ""
        soup = BeautifulSoup(r.text, "html.parser")

        # Common coupon containers
        coupon_div = soup.find(lambda tag: tag.name in ["div","span"] and tag.get("class") and any("coupon" in c.lower() or "offer" in c.lower() for c in tag.get("class")))
        if coupon_div:
            text = coupon_div.get_text(" ", strip=True)
            if extract_coupon(text) >= 500:
                return True, text

        # label text scan
        coupon_span = soup.find("span", string=lambda t: t and "coupon" in t.lower())
        if coupon_span:
            text = coupon_span.get_text(" ", strip=True)
            if extract_coupon(text) >= 500:
                return True, text

        # JSON-LD offers or embedded data
        for script in soup.find_all("script", type=lambda t: t and "json" in t):
            try:
                data = json.loads(script.get_text(strip=True))
            except:
                continue
            if isinstance(data, dict):
                blob = json.dumps(data)
                if extract_coupon(blob) >= 500:
                    return True, "JSON coupon detected"
            elif isinstance(data, list):
                blob = json.dumps(data)
                if extract_coupon(blob) >= 500:
                    return True, "JSON coupon detected"

        # Fallback: full page text
        text_all = soup.get_text(" ", strip=True)
        if extract_coupon(text_all) >= 500:
            return True, "Page coupon detected"

        return False, ""
    except Exception as e:
        print("Coupon parse error:", e)
        return False, ""

def build_alert(brand, name, price, mrp, discount_per, discount_amt, reason, link):
    title = brand or "Unknown brand"
    pname = name or "Product"
    return (
        f"🧨 <b>Loot Alert</b>\n"
        f"🧾 <b>{title}</b> — {pname}\n"
        f"💸 Price: ₹{price if price else 'N/A'} (MRP: ₹{mrp if mrp else 'N/A'})\n"
        f"📉 Discount: {discount_per}%  (₹{discount_amt})\n"
        f"🔎 Reason: {reason}\n"
        f"🔗 {link}"
    )

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
    items = soup.find_all("li", class_="product-base") or soup.find_all("li")
    alerts = 0

    for li in items:
        try:
            brand, name, price, mrp, text_lower = extract_prices_and_names(li)
            if not brand and not name and not price:
                continue

            discount_amt = 0
            discount_per = 0
            if price and mrp and mrp > price:
                discount_amt = mrp - price
                discount_per = round((discount_amt / mrp) * 100)

            is_general_glitch = (discount_per >= GENERAL_GLITCH_PERCENT) or (discount_amt >= GENERAL_GLITCH_AMOUNT)
            is_premium = is_premium_text(text_lower)
            is_special_brand = any(s in text_lower for s in ["nike","jordan","h&m","mango man","only"])
            has_coupon_keyword = contains_special_keyword(text_lower)

            # Product link
            link = ""
            a = li.find("a", href=True)
            if a:
                href = a["href"]
                link = "https://www.myntra.com" + href if href.startswith("/") else href
            else:
                link = url

            # Coupon detection (API + HTML)
            has_big_coupon, coupon_desc = fetch_coupon_data(link)
            if not has_big_coupon:
                has_big_coupon, coupon_desc = fetch_coupon_html(link)

            notify = False
            reason = ""

            if has_big_coupon or has_coupon_keyword:
                notify = True
                reason = f"Coupon detected: {coupon_desc or 'JS/HTML coupon'}"
            elif is_general_glitch:
                notify = True
                reason = f"General glitch {discount_per}% / ₹{discount_amt}"
            elif is_special_brand and (discount_per >= SPECIAL_BRAND_PERCENT or discount_amt >= SPECIAL_BRAND_AMOUNT):
                notify = True
                reason = f"Special brand ({'nike/jordan/h&m/mango man/only'}) {discount_per}% / ₹{discount_amt}"
            elif is_premium and (discount_per >= PREMIUM_PERCENT or discount_amt >= PREMIUM_AMOUNT):
                notify = True
                reason = f"Premium {discount_per}% / ₹{discount_amt}"

            if notify:
                key = f"{brand}|{name}|{price}|{mrp}|{link}"
                if key in SEEN:
                    continue
                SEEN.add(key)
                if len(SEEN) > MAX_SEEN:
                    # naive trim
                    SEEN.pop()

                send_telegram(build_alert(brand, name, price, mrp, discount_per, discount_amt, reason, link))
                alerts += 1
        except Exception as e:
            # silently skip bad tiles
            continue

    print(f"✅ Scanned {url}  — alerts: {alerts}")
    return alerts

def scan_product(product_url):
    """Single product deeplink scanner (handles coupon-only glitches)"""
    try:
        r = requests.get(product_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ {product_url} returned {r.status_code}")
            return 0
        soup = BeautifulSoup(r.text, "html.parser")

        # Basic product info
        brand = (soup.find("h1", class_=lambda c: c and "pdp-title" in c) or soup.find("h1")).get_text(strip=True) if soup.find("h1") else "Product"
        name  = (soup.find("h1", class_=lambda c: c and "pdp-name" in c) or soup.find("h2") or soup.find("h3"))
        name  = name.get_text(strip=True) if name else ""

        # Price & MRP
        price_node = soup.find("span", class_=lambda c: c and ("pdp-price" in c or "discountedPriceText" in c))
        mrp_node   = soup.find("span", class_=lambda c: c and ("pdp-mrp" in c or "strike" in c))
        price = parse_price(price_node.get_text()) if price_node else None
        mrp   = parse_price(mrp_node.get_text()) if mrp_node else None

        # Coupon detection (API + HTML)
        has_big_coupon_api, coupon_api_desc = fetch_coupon_data(product_url)
        has_big_coupon_html, coupon_html_desc = fetch_coupon_html(product_url)
        has_big_coupon = has_big_coupon_api or has_big_coupon_html
        coupon_desc = coupon_api_desc or coupon_html_desc

        # Compute discount for display (based on visible price)
        discount_amt = 0
        discount_per = 0
        if price and mrp and mrp > price:
            discount_amt = mrp - price
            discount_per = round((discount_amt / mrp) * 100)

        notify = False
        reason = ""

        if has_big_coupon:
            notify = True
            reason = f"Coupon detected: {coupon_desc or 'JS/HTML coupon'}"
        elif discount_per >= GENERAL_GLITCH_PERCENT or discount_amt >= GENERAL_GLITCH_AMOUNT:
            notify = True
            reason = f"General glitch {discount_per}% / ₹{discount_amt}"

        if notify:
            key = f"{brand}|{name}|{price}|{mrp}|{product_url}"
            if key not in SEEN:
                SEEN.add(key)
                if len(SEEN) > MAX_SEEN:
                    SEEN.pop()
                send_telegram(build_alert(brand, name, price, mrp, discount_per, discount_amt, reason, product_url))
                print(f"✅ Scanned product {product_url} — alert sent")
                return 1
        print(f"ℹ️ Scanned product {product_url} — no alert")
        return 0
    except Exception as e:
        print("Product scan error:", e)
        return 0

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
            # Categories
            for url in CATEGORY_URLS:
                scan_category(url)
            # Direct products (deeplinks)
            for purl in PRODUCT_URLS:
                scan_product(purl)
            time.sleep(30 + int(time.time()) % 31)
        except Exception as e:
            print("Scanner error:", e)
            time.sleep(60)

# Background scanner
threading.Thread(target=loop_scan, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
