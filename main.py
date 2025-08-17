import os
import requests
import time
from bs4 import BeautifulSoup
from flask import Flask
from datetime import datetime

# Flask app for Render health check
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Myntra Glitch Bot is Running!"

@app.route('/health')
def health():
    return {"status": "healthy", "time": datetime.now().isoformat()}

# Telegram config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Target premium brands
premium_brands = ["Nike", "Jordan", "Adidas", "Zara", "H&M", "Puma", "Armani Exchange", "Guess", "Calvin Klein"]

# Already sent deals (de-duplication)
sent_deals = set()

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("⚠️ Telegram Error:", e)

def check_myntra_glitches():
    url = "https://www.myntra.com/men-tshirts"  # Example category
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print("❌ Error fetching Myntra page:", r.status_code)
        return
    
    soup = BeautifulSoup(r.text, "html.parser")
    products = soup.find_all("li", {"class": "product-base"})

    for p in products:
        try:
            name = p.find("h3", {"class": "product-brand"}).text.strip()
            title = p.find("h4", {"class": "product-product"}).text.strip()
            price = int(p.find("span", {"class": "product-discountedPrice"}).text.replace("Rs. ", "").replace(",", ""))
            orig_price = int(p.find("span", {"class": "product-strike"}).text.replace("Rs. ", "").replace(",", ""))
            discount = int((orig_price - price) * 100 / orig_price)

            # Generate unique deal ID
            deal_id = f"{name}-{title}-{price}"

            # Skip duplicates
            if deal_id in sent_deals:
                continue
            sent_deals.add(deal_id)

            # Conditions
            if (name in ["Nike", "Jordan"] and discount >= 40) or \
               (discount >= 80) or \
               (name in premium_brands and (orig_price - price) >= 1000):

                message = f"🔥 Deal Found!\n\n🛍 {name} - {title}\n💰 Price: Rs.{price}\n🏷 Discount: {discount}% OFF\n🔗 https://www.myntra.com/{title.replace(' ', '-')}"
                send_telegram_message(message)
                print("✅ Alert sent:", message)

        except Exception as e:
            print("⚠️ Error parsing product:", e)

def daily_status_message():
    send_telegram_message("✅ Bot is alive & running fine on Render 🚀")

# Scheduler loop
def start_bot():
    last_status_time = 0
    while True:
        try:
            check_myntra_glitches()
        except Exception as e:
            print("⚠️ Error in bot loop:", e)

        # Send status once every 24h
        if time.time() - last_status_time > 86400:
            daily_status_message()
            last_status_time = time.time()

        time.sleep(60)  # run every 1 min

if __name__ == "__main__":
    import threading
    threading.Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
