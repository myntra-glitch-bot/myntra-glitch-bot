from flask import Flask
import os
import threading
import time
import json
import requests
from bs4 import BeautifulSoup
import re

# Flask app for Render (required for UptimeRobot)
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Myntra Glitch Bot is Live & Working!"

def start_bot():
    with open("config.json") as f:
        config = json.load(f)

    telegram_token = config["telegram_token"]
    telegram_user_id = config["telegram_user_id"]

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
    print("✅ Bot started!")

    def send_telegram(message):
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = {"chat_id": telegram_user_id
