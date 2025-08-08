import time
import json
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import random

# Config load
with open("config.json") as f:
    config = json.load(f)

telegram_token = config["telegram_token"]
telegram_user_id = config["telegram_user_id"]

# Render app ka URL yaha daal
RENDER_URL = "https://your-render-app.onrender.com"

category_urls = [
    "https://www.myntra.com/men-clothing",
    "https://www.myntra.com/women-clothing",
    "https://www.myntra.com/men-shoes",
    "https://www.myntra.com/women-footwear",
    "https://www.myntra.com/watches",
    "https://www.myntra.com/home-living"
]

premium_brands = [
    "zara", "nike", "puma", "mango", "armani", "tommy", "ck", "guess", "h&m",
    "rare rabbit", "diesel", "jack & jones", "pepe", "lee", "louis vuitton",
    "versace", "allsaints", "reebok", "superdry", "uspa", "lino", "linen",
    "roadster", "campus", "redtape", "levis", "adidas", "bata", "skechers"
]

special_keywords = [
    "coupon", "extra off", "watch", "wristwatch", "smartwatch", "leather shoes",
    "running shoes", "sneakers", "blazer", "luxury", "linen shirt", "linen pant"
]

sent_items = set()
last_ping_date = None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": telegram_user_id, "text": message}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def ping_render():
    """Render ko ping karne ka function"""
    try:
        res = requests.get(RENDER_URL, timeout=10)
        if res.status_code == 200:
            print(f"[OK] Render ping successful ({time.ctime()})")
        else:
            print(f"[FAIL] Render ping status: {res.status_code}")
    except Exception as e:
        print("[PING ERROR]", e)

print("✅ Bot started on phone!")

while True:
    try:
        # Render ko ping karo taaki wo active rahe
        ping_render()

        current_date = datetime.now().date()
        if last_ping_date != current_date:
            send_telegram("📢 Daily Ping: Myntra Glitch Bot is LIVE & Running!")
            last_ping_date = current_date

        for url in category_urls:
            headers = {"User-Agent": "Mozilla/5.0"}
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
            except Exception as e:
                print(f"⚠️ Request Error for {url}: {e}")
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            products = soup.find_all("li")

            for product in products:
                text = product.text.strip().lower()
                if not text or text in sent_items:
                    continue

                price_match = re.search(r"₹(\d{2,5})", text)
                mrp_match = re.findall(r"mrp.*?₹(\d{2,5})", text)
                price = int(price_match.group(1)) if price_match else None
                mrp = int(mrp_match[0]) if mrp_match else None

                discount_amt = (mrp - price) if (price and mrp and mrp > price) else 0
                discount_per = round((discount_amt / mrp) * 100) if (price and mrp) else 0

                is_glitch = discount_per >= 80 or discount_amt >= 1000
                is_coupon = any(word in text for word in special_keywords)
                is_premium = any(brand in text for brand in premium_brands)

                if is_glitch or (is_premium and (discount_per >= 50 or discount_amt >= 500)) or is_coupon:
                    sent_items.add(text)
                    link = url.split("?")[0]
                    message = f"🧨 Loot Alert 🛍️\n\n{text[:300]}\n\n🔗 {link}"
                    send_telegram(message)

            print(f"✅ Scanned: {url}")

        time.sleep(random.randint(30, 60))  # Random delay

    except Exception as e:
        print("⚠️ Main Loop Error:", e)
        time.sleep(60)
