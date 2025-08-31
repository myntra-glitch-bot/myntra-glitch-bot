import os
import json
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

# ------------------- Load Config -------------------
with open("config.json", "r") as f:
    config = json.load(f)

BOT_TOKEN = os.getenv("BOT_TOKEN", config.get("BOT_TOKEN"))
CHAT_ID = os.getenv("CHAT_ID", config.get("CHAT_ID"))
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", config.get("SCAN_INTERVAL", 60)))

# ------------------- Brand Rules -------------------
priority_brands = [
    "Nike", "Adidas", "Puma", "H&M", "Zara"
]

premium_brands = [
    "Armani Exchange", "Guess", "Louis Vuitton", "Mango Man", "Rare Rabbit",
    "Tommy Hilfiger", "Calvin Klein", "Diesel", "AllSaints", "Versace",
    "Jack & Jones", "Pepe Jeans", "Lee", "Linen Club"
]

special_categories = ["shoes", "watches", "luxury", "pure linen"]

# ------------------- Telegram Alert -------------------
def send_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ------------------- Scraper Logic -------------------
def check_myntra_glitches():
    print("🔍 Scanning Myntra for glitches...")
    try:
        url = "https://www.myntra.com/men-tshirts"  # Example category
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print("Failed to fetch Myntra page")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        products = soup.find_all("li", {"class": "product-base"})

        for product in products:
            try:
                brand = product.find("h3", {"class": "product-brand"}).get_text(strip=True)
                name = product.find("h4", {"class": "product-product"}).get_text(strip=True)
                price = product.find("span", {"class": "product-discountedPrice"})
                orig_price = product.find("span", {"class": "product-strike"})
                discount = product.find("span", {"class": "product-discountPercentage"})
                link = "https://www.myntra.com/" + product.find("a", href=True)["href"]

                if not price:
                    continue

                price = int(price.get_text().replace("₹", "").replace(",", ""))
                orig_price = int(orig_price.get_text().replace("₹", "").replace(",", "")) if orig_price else price
                discount_percent = int(discount.get_text().replace("% OFF", "")) if discount else 0

                # -------- Glitch / Rule Detection --------
                is_glitch = False
                reason = ""

                if brand in priority_brands and discount_percent >= 60:
                    is_glitch = True
                    reason = "🔥 Priority Brand 60%+"
                elif brand in premium_brands and discount_percent >= 70:
                    is_glitch = True
                    reason = "💎 Premium Brand 70%+"
                elif discount_percent >= 80:
                    is_glitch = True
                    reason = "⚡ 80%+ Discount"
                elif price <= 199 and discount_percent >= 70:
                    is_glitch = True
                    reason = "💥 ₹199 Super Loot"
                elif any(cat in name.lower() for cat in special_categories) and discount_percent >= 60:
                    is_glitch = True
                    reason = "⭐ Special Category Loot"

                # -------- Alert --------
                if is_glitch:
                    message = (
                        f"{reason}\n"
                        f"<b>{brand}</b> - {name}\n"
                        f"Price: ₹{price}  (MRP: ₹{orig_price}, {discount_percent}% OFF)\n"
                        f"<a href='{link}'>Grab Now 🔗</a>"
                    )
                    print("ALERT:", message)
                    send_telegram(message)

            except Exception as e:
                print("Parse error:", e)

    except Exception as e:
        print("Scraper error:", e)

# ------------------- Background Loop -------------------
def background_task():
    while True:
        check_myntra_glitches()
        time.sleep(SCAN_INTERVAL)

# ------------------- Flask App -------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Myntra Glitch Bot Running with Flask + Thread"

# ------------------- Start Bot -------------------
if __name__ == "__main__":
    t = threading.Thread(target=background_task, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
