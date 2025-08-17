def extract_coupon_from_html(li):
    """Try to extract coupon/offer text from product HTML card"""
    try:
        coupon_tag = li.find("span", {"class": "couponsList-base-discount"}) \
                  or li.find("div", {"class": "couponsList-base-offer"}) \
                  or li.find("span", string=re.compile(r"Extra", re.I)) \
                  or li.find("span", string=re.compile(r"Coupon", re.I))
        if coupon_tag:
            return coupon_tag.get_text(strip=True)
    except:
        return None
    return None


def scan_category(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ {url} returned {r.status_code}")
            return 0
    except Exception as e:
        print("Request failed:", e)
        return 0

    soup = BeautifulSoup(r.text, "lxml")
    items = soup.find_all("li", class_="product-base") or soup.find_all("li")
    alerts = 0

    for li in items:
        try:
            brand, name, price, mrp, text_lower = extract_prices_and_names(li)
            if not brand and not name and not price: 
                continue

            discount_amt = 0
            discount_per = 0
            if price and mrp and mrp > price:
                discount_amt = mrp - price
                discount_per = round((discount_amt / mrp) * 100)

            is_general_glitch = (discount_per >= GENERAL_GLITCH_PERCENT) or (discount_amt >= GENERAL_GLITCH_AMOUNT)
            is_premium = is_premium_text(text_lower)
            is_special_brand = any(s in text_lower for s in ["nike","jordan","h&m","mango man","only"])
            has_coupon_keyword = contains_special_keyword(text_lower)

            # ----- Product link -----
            link = ""
            a = li.find("a", href=True)
            if a:
                href = a["href"]
                if href.startswith("/"): 
                    link = "https://www.myntra.com" + href
                else: 
                    link = href
            else: 
                link = url

            # ✅ Coupon checks (API + HTML)
            has_big_coupon, coupon_desc = fetch_coupon_data(link)
            html_coupon = extract_coupon_from_html(li)

            notify = False
            reason = ""

            if has_big_coupon:
                notify = True
                reason = f"Coupon detected via API: {coupon_desc}"
            elif html_coupon:
                notify = True
                reason = f"Coupon detected via HTML: {html_coupon}"
            elif has_coupon_keyword:
                notify = True
                reason = f"Coupon keyword found in text"
            elif is_general_glitch:
                notify = True
                reason = f"General glitch {discount_per}% / ₹{discount_amt}"
            elif is_special_brand and (discount_per >= SPECIAL_BRAND_PERCENT or discount_amt >= SPECIAL_BRAND_AMOUNT):
                notify = True
                reason = f"Special brand ({'nike/jordan/h&m/mango man/only'}) {discount_per}% / ₹{discount_amt}"
            elif is_premium and (discount_per >= PREMIUM_PERCENT or discount_amt >= PREMIUM_AMOUNT):
                notify = True
                reason = f"Premium {discount_per}% / ₹{discount_amt}"

            if notify:
                key = f"{brand}|{name}|{price}|{mrp}"
                if key in SEEN: 
                    continue
                SEEN.add(key)
                if len(SEEN) > MAX_SEEN:
                    for _ in range(len(SEEN)-MAX_SEEN): 
                        SEEN.pop()

                title = brand or "Unknown brand"
                pname = name or "Product"
                message = (
                    f"🧨 <b>Loot Alert</b>\n"
                    f"🧾 <b>{title}</b> — {pname}\n"
                    f"💸 Price: ₹{price if price else 'N/A'} (MRP: ₹{mrp if mrp else 'N/A'})\n"
                    f"📉 Discount: {discount_per}%  (₹{discount_amt})\n"
                    f"🔎 Reason: {reason}\n"
                    f"🔗 {link}"
                )
                send_telegram(message)
                alerts += 1
        except Exception as e:
            print("Parse error:", e)
            continue

    print(f"✅ Scanned {url}  — alerts: {alerts}")
    return alerts
