import requests
from bs4 import BeautifulSoup
import time
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

def scrape_myntra():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    url = "https://www.myntra.com/men-clothing"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    items = soup.find_all("li", {"class": "product-base"})

    for item in items:
        try:
            brand = item.find("h3", {"class": "product-brand"}).text.strip()
            name = item.find("h4", {"class": "product-product"}).text.strip()
            price_tag = item.find("span", {"class": "product-discountedPrice"})
            original_price_tag = item.find("span", {"class": "product-strike"})

            if price_tag and original_price_tag:
                price = int(price_tag.text.strip("Rs. ").replace(",", ""))
                original_price = int(original_price_tag.text.strip("Rs. ").replace(",", ""))
                discount_percent = round((original_price - price) / original_price * 100)

                if discount_percent >= 80:
                    product_link = "https://www.myntra.com" + item.find("a")["href"]
                    message = f"🔥 {brand} {name}\nPrice: ₹{price} (Original: ₹{original_price})\nDiscount: {discount_percent}%\nLink: {product_link}"
                    send_telegram_message(message)
        except:
            continue

if __name__ == "__main__":
    while True:
        scrape_myntra()
        time.sleep(120)
