import requests
from bs4 import BeautifulSoup
import time
import logging
import json
import random
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# ---------- Load Config ----------
with open("config.json", "r") as f:
    config = json.load(f)

TELEGRAM_TOKEN = config["telegram_token"]   # fixed key
USER_IDS = [config["telegram_user_id"]]     # list bana diya
URLS = config["urls"]                       # category URLs
CATEGORIES = config.get("categories", {})   # optional categories block

bot = Bot(token=TELEGRAM_TOKEN)

# ---------- Logging ----------
logging.basicConfig(
    filename="lootbot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

last_report_time = None
scan_count = 0
alert_count = 0
category_alerts = {"very_special": 0, "special": 0, "premium": 0, "general": 0}


# ---------- Telegram Alert ----------
def send_alert(product, reason, category):
    global alert_count
    alert_count += 1
    category_alerts[category] += 1

    message = (
        f"📢 {reason}\n"
        f"👟 Product: {product['name']}\n"
        f"💰 Price: ₹{product['price']}\n"
        f"🏷 Discount: {product['discount']}%\n"
        f"📂 Category: {category.upper()}"
    )

    keyboard = [[InlineKeyboardButton("Open Deal 🔗", url=product['url'])]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for uid in USER_IDS:
        try:
            bot.send_message(chat_id=uid, text=message, reply_markup=reply_markup)
        except TelegramError as e:
            logging.error(f"Telegram error: {e}")


# ---------- Fetch HTML ----------
def fetch_page(url, retries=3):
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logging.warning(f"Fetch error {e}, retrying... ({attempt+1})")
            time.sleep(2 * (attempt+1))
    return None


# ---------- Parse Products ----------
def parse_products(html):
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for item in soup.select("li.product-base"):
        try:
            brand = item.select_one("h3.product-brand").get_text(strip=True)
            product_name = item.select_one("h4.product-product").get_text(strip=True)
            price = int(item.select_one("span.product-discountedPrice").get_text(strip=True).replace("₹", "").replace(",", ""))
            discount_tag = item.select_one("span.product-discountPercentage")
            discount = int(discount_tag.get_text(strip=True).replace("% OFF", "")) if discount_tag else 0
            url = "https://www.myntra.com" + item.select_one("a")["href"]

            products.append({
                "name": f"{brand} {product_name}",
                "price": price,
                "discount": discount,
                "url": url
            })
        except Exception as e:
            logging.warning(f"Parse error: {e}")
    return products


# ---------- Classification ----------
def classify_and_alert(product):
    name = product["name"].lower()

    # --- Very Special ---
    if any(b in name for b in CATEGORIES.get("very_special", [])):
        if product["discount"] >= 20 or product["price"] <= 2000:
            send_alert(product, "🔥 VERY SPECIAL LOOT FOUND", "very_special")

    # --- Special ---
    elif any(b in name for b in CATEGORIES.get("special", [])):
        if product["discount"] >= 50 or product["price"] <= 1500:
            send_alert(product, "⭐ SPECIAL LOOT FOUND", "special")

    # --- Premium ---
    elif any(b in name for b in CATEGORIES.get("premium", [])):
        if product["discount"] >= 70:
            send_alert(product, "💎 PREMIUM LOOT FOUND", "premium")

    # --- General ---
    else:
        if product["discount"] >= 80 or product["price"] <= 499:
            send_alert(product, "⚡ GENERAL GLITCH", "general")


# ---------- Daily Report ----------
def daily_report():
    global last_report_time, scan_count, alert_count, category_alerts
    now = datetime.now()
    if last_report_time is None or (now - last_report_time).seconds >= 86400:
        report = (
            "📊 Daily Report\n"
            f"👀 Total scanned: {scan_count}\n"
            f"🧨 Alerts sent: {alert_count}\n"
            f"🔥 Very Special: {category_alerts['very_special']}\n"
            f"⭐ Special: {category_alerts['special']}\n"
            f"💎 Premium: {category_alerts['premium']}\n"
            f"⚡ General: {category_alerts['general']}"
        )
        for uid in USER_IDS:
            bot.send_message(chat_id=uid, text=report)
        last_report_time = now
        scan_count = alert_count = 0
        category_alerts = {"very_special": 0, "special": 0, "premium": 0, "general": 0}


# ---------- Main Loop ----------
def main():
    global scan_count
    while True:
        for url in URLS:
            html = fetch_page(url)
            if not html:
                continue
            products = parse_products(html)
            scan_count += len(products)

            for product in products:
                classify_and_alert(product)

        daily_report()
        time.sleep(random.randint(30, 60))  # random delay to avoid blocking


if __name__ == "__main__":
    main()
