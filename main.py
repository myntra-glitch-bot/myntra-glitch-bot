import requests
from bs4 import BeautifulSoup
import time
import json
import os

# Load config.json (Telegram Bot Token + User ID)
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["BOT_TOKEN"]
USER_ID = config["USER_ID"]

# Priority 5 brands (Rule 1)
priority_brands = ["nike", "jordan", "h&m", "mango man", "zara"]

# Premium 28 brands (Rule 2)
premium_brands = [
    "adidas", "puma", "only", "armani exchange", "guess", "rare rabbit",
    "tommy hilfiger", "ck", "diesel", "allsaints", "versace",
    "jack & jones", "pepe jeans", "lee", "louis vuitton", "flying machine",
    "wrogn", "pure cotton", "gant", "banana club", "snitch",
    "mr bowerbird", "gap", "new balance", "asics", "bear house", "next", "either"
]

# Special categories (Rule 3)
special_categories = [
    "https://www.myntra.com/men-clothing",
    "https://www.myntra.com/women-clothing",
    "https://www.myntra.com/men-footwear",
    "https://www.myntra.com/women-footwear",
    "https://www.myntra.com/men-watches",
    "https://www.myntra.com/women-watches"
]

# Price history file
PRICE_HISTORY_FILE = "price_history.json"

# Load or initialize price history
if os.path.exists(PRICE_HISTORY_FILE):
    with open(PRICE_HISTORY_FILE, "r") as f:
        price_history = json.load(f)
else:
    price_history = {}

# Save price history
def save_price_history():
    with open(PRICE_HISTORY_FILE, "w") as f:
        json.dump(price_history, f)

# Send Telegram Alert
def send_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": USER_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Error sending alert:", e)

# Scraper Function
def scrape_page(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error {response.status_code} while fetching {url}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find_all("li", {"class": "product-base"})

# Apply rules
def process_product(product, category_url):
    global price_history
    try:
        brand = product.find("h3", {"class": "product-brand"}).text.strip().lower()
        title = product.find("h4", {"class": "product-product"}).text.strip()

        price = product.find("span", {"class": "product-discountedPrice"})
        original_price = product.find("span", {"class": "product-strike"})
        discount = product.find("span", {"class": "product-discountPercentage"})

        if not (price and original_price and discount):
            return

        price = int(price.text.replace("Rs.", "").replace(",", "").strip())
        original_price = int(original_price.text.replace("Rs.", "").replace(",", "").strip())
        discount_value = int(discount.text.replace("(", "").replace("% OFF)", "").strip())

        product_url = "https://www.myntra.com/" + product.find("a")["href"]

        # ---------------- PRICE DROP DETECTOR ----------------
        last_price = price_history.get(product_url, None)
        if last_price and last_price - price >= 500:
            send_alert(f"📉 Sudden Price Drop!\n\n<b>{brand.title()} - {title}</b>\nDropped: Rs.{last_price - price}\nNew Price: Rs.{price}\nOld Price: Rs.{last_price}\n👉 {product_url}")

        # Update price history
        price_history[product_url] = price
        save_price_history()

        # ---------------- APPLY RULES ----------------

        # Rule 1: Priority brands (≥30% or coupon or glitch)
        if any(b in brand for b in priority_brands):
            if discount_value >= 30:
                send_alert(f"🔥 Priority Brand Loot!\n\n<b>{brand.title()} - {title}</b>\nDiscount: {discount_value}%\nPrice: Rs.{price}\nOriginal: Rs.{original_price}\n👉 {product_url}")

        # Rule 2: Premium brands (≥60% or coupon or glitch)
        elif any(b in brand for b in premium_brands):
            if discount_value >= 60:
                send_alert(f"💎 Premium Brand Loot!\n\n<b>{brand.title()} - {title}</b>\nDiscount: {discount_value}%\nPrice: Rs.{price}\nOriginal: Rs.{original_price}\n👉 {product_url}")

        # Rule 3: Other brands but only in special categories (80–90% discount)
        elif category_url in special_categories and 80 <= discount_value <= 90:
            send_alert(f"⚡ Special Category Loot!\n\n<b>{brand.title()} - {title}</b>\nDiscount: {discount_value}%\nPrice: Rs.{price}\nOriginal: Rs.{original_price}\n👉 {product_url}")

        # Rule 4: Apply coupon detection
        coupon = product.find("span", string=lambda x: x and "coupon" in x.lower())
        if coupon:
            send_alert(f"🎟 Coupon Found!\n\n<b>{brand.title()} - {title}</b>\nDiscount: {discount_value}% + Extra Coupon\nPrice: Rs.{price}\nOriginal: Rs.{original_price}\n👉 {product_url}")

    except Exception as e:
        return

# Main Loop
def main():
    urls = special_categories + ["https://www.myntra.com/men", "https://www.myntra.com/women"]
    while True:
        for url in urls:
            print(f"Checking {url}...")
            products = scrape_page(url)
            for product in products:
                process_product(product, url)
        time.sleep(60)  # Run every 1 min

if __name__ == "__main__":
    main()
