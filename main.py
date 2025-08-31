import requests
from bs4 import BeautifulSoup
import time
import threading
from flask import Flask
import os

# Telegram config (Railway/Render me env vars set karo)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Flask app init
app = Flask(__name__)

# Myntra categories (expand kar sakte ho)
CATEGORIES = [
    "https://www.myntra.com/men-tshirts",
    "https://www.myntra.com/men-casual-shirts",
    "https://www.myntra.com/men-jeans",
    "https://www.myntra.com/men-shoes",
    "https://www.myntra.com/women-dresses",
    "https://www.myntra.com/women-tops"
]

# Already sent items store karne ke liye
sent_items = set()

def send_telegram(message):
    """Send alert to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Error:", e)

def check_glitches():
    """Scrape Myntra for big discounts"""
    for category in CATEGORIES:
        try:
            r = requests.get(category, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            products = soup.find_all("li", {"class": "product-base"})
            
            for p in products:
                name = p.find("h3").get_text(strip=True)
                brand = p.find("h4").get_text(strip=True)
                price = p.find("span", {"class": "product-discountedPrice"})
                orig = p.find("span", {"class": "product-strike"})
                disc = p.find("span", {"class": "product-discountPercentage"})
                link = "https://www.myntra.com" + p.find("a")["href"]

                if price and orig and disc:
                    price_val = int(price.get_text().replace("Rs. ", "").replace(",", ""))
                    orig_val = int(orig.get_text().replace("Rs. ", "").replace(",", ""))
                    discount_val = int(disc.get_text().replace("(", "").replace("% OFF)", ""))

                    # Condition for glitch (80%+ off or ₹99 items)
                    if (discount_val >= 80 or price_val <= 199) and link not in sent_items:
                        sent_items.add(link)
                        msg = f"🔥 Glitch Found!\n{brand} - {name}\nPrice: ₹{price_val} (₹{orig_val})\nDiscount: {discount_val}% OFF\n{link}"
                        send_telegram(msg)

        except Exception as e:
            print("Scraping error:", e)

def run_checker():
    """Background loop"""
    while True:
        check_glitches()
        time.sleep(30)  # check every 30 sec

@app.route('/')
def home():
    return "Myntra Glitch Bot is Running ✅"

@app.route('/ping')
def ping():
    return "pong"

# Start background thread
threading.Thread(target=run_checker, daemon=True).start()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
