import time
import json
import requests
from bs4 import BeautifulSoup
import re
from flask import Flask
import os
import threading
from datetime import datetime

# Load config
with open("config.json") as f:
    config = json.load(f)

telegram_token = config["telegram_token"]
telegram_user_id = config["telegram_user_id"]

# Flask App to keep Render alive
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Myntra Glitch Bot is Live & Working!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Start Flask in background
threading.Thread(target=run_flask).start()

# Category URLs to scan
category_urls = [
    "https://www.myntra.com/men-clothing",
    "https://www.myntra.com/women-clothing",
    "https://www.myntra.com/men-shoes",
    "https://www.myntra.com/women-footwear",
    "https://www.myntra.com/watches",
    "https://www.myntra.com/home-living"
]

# Premium brands list
premium_brands = [
    "zara", "nike", "puma", "mango", "armani", "tommy", "ck", "guess", "h&m",
    "rare rabbit", "diesel", "jack & jones", "pepe", "lee", "louis vuitton",
    "versace", "allsaints", "reebok", "superdry", "uspa", "lino", "linen",
    "roadster", "campus", "redtape", "levis", "adidas", "bata", "skechers"
]

# Keywords to detect glitch/coupon
special_keywords = [
    "coupon", "extra off", "watch", "wristwatch", "smartwatch", "leather shoes",
    "running shoes", "sneakers", "blazer", "luxury", "linen shirt", "linen pant"
]

sent_items = set()
print("✅ Bot started!")

# Daily ping tracker
last_ping_date = None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {"chat_id": telegram_user_id, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

while True:
    try:
        current_date = datetime.now().date()

        # ✅ Daily ping once per day
        if last_ping_date != current_date:
            send_telegram("📢 Daily Ping: Myntra Glitch Bot is LIVE & Running!")
            last_ping_date = current_date

        for url in category_urls:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
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

        time.sleep(30)

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(60)
