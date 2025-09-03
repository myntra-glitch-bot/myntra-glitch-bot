import json
import requests
from bs4 import BeautifulSoup
from flask import Flask
import threading
import time
import logging
import random
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# -------------------- Load Config --------------------
with open("config.json", "r") as f:
    config = json.load(f)

TELEGRAM_TOKEN = config["telegram_token"]
TELEGRAM_USER_ID = config["telegram_user_id"]
CATEGORIES = config["categories"]

bot = Bot(token=TELEGRAM_TOKEN)

# -------------------- Logging --------------------
logging.basicConfig(
    filename="lootbot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -------------------- Brand Groups --------------------
VERY_SPECIAL = ["nike", "jordan", "zara"]
SPECIAL = ["rare rabbit", "mango man", "ether", "mr bowerbird", "h&m", "adidas original"]
PREMIUM = ["armani", "tommy", "ck", "guess", "pepe", "lee", "levis", "gap",
           "snitch", "gant", "next", "mr bowerbird", "jack & jones", "puma",
           "asics", "new balance"]

# -------------------- Flask App --------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🔥 Myntra Hacker Bot 24x7 Running with Gunicorn", 200

# -------------------- Telegram --------------------
def send_alert(product, reason, category, offers):
    message = (
        f"{reason}\n"
        f"👟 {product['brand'].title()} - {product['name']}\n"
        f"💰 Price: ₹{product['price']} (MRP {product['orig_price']})\n"
        f"🔖 Discount: {product['discount']}%\n"
        f"💡 Offers: {', '.join(offers) if offers else 'None'}\n"
        f"📌 Category: {category}\n"
    )

    keyboard = [[InlineKeyboardButton("Open Deal 🔗", url=product['url'])]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        bot.send_message(chat_id=TELEGRAM_USER_ID, text=message, reply_markup=reply_markup)
        logging.info(f"Alert sent: {product['brand']} - {reason}")
    except TelegramError as e:
        logging.error(f"Telegram error: {e}")

# -------------------- Fetch Page with Retry --------------------
def fetch_page(url, retries=3):
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                return r.text
            else:
                logging.warning(f"Bad status {r.status_code} for {url}")
        except Exception as e:
            logging.warning(f"Fetch error {e}, retry {attempt+1}")
            time.sleep(2 * (attempt+1))
    return None

# -------------------- Scraper --------------------
def scrape_category(category_url, category_name):
    html = fetch_page(category_url)
    if not html:
        return

    soup = BeautifulSoup(html, "lxml")
    products = soup.find_all("li", {"class": "product-base"})

    for p in products:
        try:
            name_tag = p.find("h4", {"class": "product-product"})
            brand_tag = p.find("h3", {"class": "product-brand"})
            price_tag = p.find("span", {"class": "product-discountedPrice"})
            orig_price_tag = p.find("span", {"class": "product-strike"})
            discount_tag = p.find("span", {"class": "product-discountPercentage"})

            if not name_tag or not brand_tag:
                continue

            product_name = name_tag.text.strip()
            brand = brand_tag.text.strip().lower()
            price = int(price_tag.text.replace("₹", "").replace(",", "")) if price_tag else 0
            orig_price = orig_price_tag.text.strip() if orig_price_tag else "N/A"
            discount = int(discount_tag.text.replace("% OFF", "").strip()) if discount_tag else 0

            # Offer detection
            offer_texts = []
            for span in p.find_all("span"):
                t = span.text.lower()
                if "bank" in t or "coupon" in t or "offer" in t:
                    offer_texts.append(t)

            product_url = "https://www.myntra.com" + p.find("a")["href"]

            product = {
                "name": product_name,
                "brand": brand,
                "price": price,
                "orig_price": orig_price,
                "discount": discount,
                "url": product_url
            }

            # -------------------- RULES --------------------
            reason = None
            if brand in [b.lower() for b in VERY_SPECIAL]:
                if discount >= 20 or offer_texts:
                    reason = "🔥 VERY SPECIAL LOOT"
            elif brand in [b.lower() for b in SPECIAL]:
                if discount >= 50 or offer_texts:
                    reason = "⭐ SPECIAL LOOT"
            elif brand in [b.lower() for b in PREMIUM]:
                if discount >= 70 or offer_texts:
                    reason = "💎 PREMIUM LOOT"
            else:  # NORMAL
                if discount >= 80 or price <= 499 or offer_texts:
                    reason = "⚡ GENERAL GLITCH"

            # -------------------- ALERT --------------------
            if reason:
                send_alert(product, reason, category_name, offer_texts)

        except Exception as e:
            logging.warning(f"Parse Error: {e}")

# -------------------- Main Loop --------------------
def start_scraper():
    while True:
        for cat in CATEGORIES:
            scrape_category(cat["url"], cat["name"])
        time.sleep(random.randint(30, 60))  # Random delay

# -------------------- Background Thread --------------------
t = threading.Thread(target=start_scraper, daemon=True)
t.start()

# -------------------- Run Flask --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
