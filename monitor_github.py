import os
import sys
import json
import urllib.request
import urllib.parse
import re
from datetime import datetime

# Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen_ads.json")

# Config from Environment variables
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

SEARCH_URL = "https://www.olx.ua/d/uk/list/q-lucky-pin/?search%5Border%5D=created_at%3Adesc"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def send_telegram_message(text):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram credentials not configured. Skipping notification.")
        return False
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Error sending to Telegram: {e}", file=sys.stderr)
        return False

def fetch_ads():
    req = urllib.request.Request(SEARCH_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Network error fetching OLX: {e}", file=sys.stderr)
        return []

    m = re.search(r'window\.__PRERENDERED_STATE__\s*=\s*(".*?"|\{.*?\});', html)
    if not m:
        print("Could not find __PRERENDERED_STATE__", file=sys.stderr)
        return []

    raw = m.group(1)
    if raw.startswith('"'):
        data_str = json.loads(raw)
        data = json.loads(data_str) if isinstance(data_str, str) else data_str
    else:
        data = json.loads(raw)

    ads_raw = data.get("listing", {}).get("listing", {}).get("ads", [])
    parsed_ads = []
    for ad in ads_raw:
        ad_id = str(ad.get("id"))
        title = ad.get("title", "")
        price_info = ad.get("price", {})
        price = price_info.get("displayValue", "Ціна не вказана") if isinstance(price_info, dict) else "Ціна не вказана"
        url = ad.get("url", "")
        location_data = ad.get("location", {})
        city_name = location_data.get("cityName", "") if isinstance(location_data, dict) else ""
        
        parsed_ads.append({
            "id": ad_id,
            "title": title,
            "price": price,
            "url": url,
            "city": city_name,
            "discovered_at": datetime.now().isoformat()
        })
    return parsed_ads

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

def main():
    seen = load_seen()
    ads = fetch_ads()
    print(f"Fetched {len(ads)} ads from OLX.")

    # First run initialization if file was empty
    if not seen and ads:
        print("First run: saving baseline ads without spamming notifications...")
        for ad in ads:
            seen[ad["id"]] = {
                "title": ad["title"],
                "price": ad["price"],
                "url": ad["url"],
                "city": ad["city"]
            }
        save_seen(seen)
        print(f"Baseline saved: {len(seen)} ads.")
        return

    new_ads = []
    for ad in ads:
        if ad["id"] not in seen:
            new_ads.append(ad)
            seen[ad["id"]] = {
                "title": ad["title"],
                "price": ad["price"],
                "url": ad["url"],
                "city": ad["city"]
            }

    if new_ads:
        print(f"Found {len(new_ads)} new ad(s)!")
        for ad in new_ads:
            msg = (
                f"🔔 <b>Нове оголошення на OLX!</b>\n\n"
                f"📌 <b>{ad['title']}</b>\n"
                f"💰 <b>Ціна:</b> {ad['price']}\n"
                f"📍 <b>Місто:</b> {ad['city']}\n\n"
                f"🔗 <a href='{ad['url']}'>Переглянути на OLX</a>"
            )
            send_telegram_message(msg)
        save_seen(seen)
    else:
        print("No new ads found.")

if __name__ == "__main__":
    main()
