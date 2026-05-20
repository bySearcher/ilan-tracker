#!/usr/bin/env python3
"""
ilan.gov.tr Akademik Kadro Takip Botu - v2 (Selenium)
JavaScript ile yüklenen sayfayı headless Chrome ile tarar.
"""

import os, json, hashlib, time, requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ── Ayarlar ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KEYWORDS = [
    "moleküler biyoloji",
    "moleküler biyoloji ve genetik",
    "molecular biology",
    "mbg",
    "genetik",
]

BASE_URL   = "https://www.ilan.gov.tr"
SEARCH_URL = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"
SEEN_FILE  = "data/seen_ids.json"

# TEST MODU: True iken tüm ilanları eşleştir (ilk çalıştırmada True bırakın)
TEST_MODE = True

# ── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen_ids(ids):
    os.makedirs("data", exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

def make_id(title, url):
    return hashlib.md5(f"{title}|{url}".encode()).hexdigest()

def matches_keywords(text):
    if TEST_MODE:
        return True
    return any(kw in text.lower() for kw in KEYWORDS)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=15)
    resp.raise_for_status()
    print(f"[Telegram] Gönderildi: {message[:60]}...")

def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=tr-TR")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)

# ── Tarama ───────────────────────────────────────────────────────────────────

def fetch_listings_selenium(driver, page=1):
    url = f"{SEARCH_URL}?page={page}" if page > 1 else SEARCH_URL
    print(f"[Sayfa {page}] Yükleniyor: {url}")
    driver.get(url)

    # JS yüklenene kadar bekle — ilan listesi veya "ilan bulunamadı" mesajı
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                "a[href*='/ilan/'], .ilan-item, .listing-item, app-ilan, [class*='ilan']"))
        )
    except Exception:
        print(f"[Sayfa {page}] Bekleme timeout — sayfayı yine de okuyorum.")

    time.sleep(3)  # Ekstra bekleme (lazy load için)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Debug: tüm class'ları yazdır (ilk çalıştırmada faydalı)
    all_classes = set()
    for tag in soup.find_all(class_=True):
        for cls in tag.get("class", []):
            all_classes.add(cls)
    print(f"[Sayfa {page}] Bulunan class'lar: {sorted(all_classes)[:30]}")

    listings = []

    # Strateji 1: /ilan/ içeren tüm linkleri tara
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/ilan/" not in href or "/kategori/" in href:
            continue
        full_url = href if href.startswith("http") else BASE_URL + href
        title = a.get_text(strip=True)
        # Çok kısa başlıkları atla (navigasyon linkleri olabilir)
        if len(title) > 15:
            listings.append({"title": title, "url": full_url, "detail": ""})

    # Strateji 2: Kart/liste yapıları
    if not listings:
        for selector in [
            "[class*='ilan-item']", "[class*='list-item']",
            "[class*='card']", "article", "li[class*='ilan']",
            "app-ilan-liste-item", "app-ilan",
        ]:
            cards = soup.select(selector)
            for card in cards:
                link = card.find("a", href=True)
                if not link:
                    continue
                href = link.get("href", "")
                full_url = href if href.startswith("http") else BASE_URL + href
                title = card.get_text(strip=True)[:200]
                if len(title) > 15:
                    listings.append({"title": title, "url": full_url, "detail": ""})
            if listings:
                break

    print(f"[Sayfa {page}] {len(listings)} ilan bulundu.")
    return listings

def format_notification(ilan):
    return (
        f"🎓 <b>Yeni Akademik İlan!</b>\n\n"
        f"📌 <b>{ilan['title'][:200]}</b>\n"
        f"🔗 <a href=\"{ilan['url']}\">İlana Git →</a>\n\n"
        f"🏷️ #MolekulerBiyoloji #AkademikIlan #ilangovtr"
    )

# ── Ana Çalışma ──────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Tarama başlıyor...")
    seen_ids = load_seen_ids()
    driver = get_driver()
    all_listings = []

    try:
        for page in range(1, 6):  # İlk 5 sayfa
            listings = fetch_listings_selenium(driver, page)
            if not listings:
                print(f"[Sayfa {page}] Boş, duruyorum.")
                break
            all_listings.extend(listings)
            time.sleep(2)
    finally:
        driver.quit()

    print(f"\nToplam {len(all_listings)} ilan tarandı.")

    new_count = 0
    for ilan in all_listings:
        if not matches_keywords(f"{ilan['title']} {ilan.get('detail','')}"):
            continue

        ilan_id = make_id(ilan["title"], ilan["url"])
        if ilan_id in seen_ids:
            print(f"  [Zaten görüldü] {ilan['title'][:60]}")
            continue

        print(f"  [YENİ] {ilan['title'][:60]}")
        try:
            send_telegram(format_notification(ilan))
            seen_ids.add(ilan_id)
            new_count += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [Telegram Hatası] {e}")

        if TEST_MODE and new_count >= 3:
            print("TEST MODU: 3 ilan gönderildi, duruyorum.")
            break

    save_seen_ids(seen_ids)

    # Özet
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    if new_count == 0:
        msg = (f"🔍 <b>Tarama Tamamlandı</b>\n🕐 {now}\n"
               f"📊 {len(all_listings)} ilan tarandı\n✅ Yeni ilan yok.")
    else:
        msg = (f"🔍 <b>Tarama Tamamlandı</b>\n🕐 {now}\n"
               f"📊 {len(all_listings)} ilan tarandı\n"
               f"🆕 <b>{new_count} yeni ilan bildirildi!</b>")
    send_telegram(msg)
    print(f"Bitti. {new_count} yeni ilan.")

if __name__ == "__main__":
    main()
