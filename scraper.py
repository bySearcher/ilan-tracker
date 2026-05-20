#!/usr/bin/env python3
"""
ilan.gov.tr Akademik Kadro Takip Botu - v3
Tablo yapısını parse eder, ilan numarasından URL oluşturur.
"""

import os, json, hashlib, time, requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
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
TEST_MODE  = False   # Test bitti, False bırakın

# ─────────────────────────────────────────────────────────────────────────────

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen_ids(ids):
    os.makedirs("data", exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

def make_id(ilan_no, title):
    return hashlib.md5(f"{ilan_no}|{title}".encode()).hexdigest()

def matches_keywords(text):
    if TEST_MODE:
        return True
    return any(kw in text.lower() for kw in KEYWORDS)

def send_telegram(message):
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message,
              "parse_mode": "HTML", "disable_web_page_preview": False},
        timeout=15
    )
    resp.raise_for_status()
    print(f"[Telegram] Gönderildi: {message[:80]}...")

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

# ─────────────────────────────────────────────────────────────────────────────

def fetch_page(driver, page=1):
    url = f"{SEARCH_URL}?page={page}" if page > 1 else SEARCH_URL
    print(f"[Sayfa {page}] {url}")
    driver.get(url)

    # "Toplam X ilan" yazısının gelmesini bekle
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//*[contains(text(),'Toplam') and contains(text(),'ilan')]"))
        )
    except Exception:
        pass
    time.sleep(4)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    listings = []

    # ── Strateji 1: tablo satırları (tr > td) ────────────────────────────────
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Sütun sırası: Kurum | Başlık | İlan No | Şehir
        kurum    = texts[0] if len(texts) > 0 else ""
        baslik   = texts[1] if len(texts) > 1 else ""
        ilan_no  = texts[2] if len(texts) > 2 else ""
        sehir    = texts[3] if len(texts) > 3 else ""

        if not baslik or not ilan_no:
            continue

        # İlan linkini direkt hücreden al
        link_el = row.find("a", href=True)
        if link_el:
            href = link_el["href"]
            ilan_url = href if href.startswith("http") else BASE_URL + href
        else:
            # Link yoksa ilan numarasından URL oluştur
            ilan_url = f"{BASE_URL}/ilan/{ilan_no.lower()}"

        listings.append({
            "kurum":   kurum,
            "title":   baslik,
            "ilan_no": ilan_no,
            "sehir":   sehir,
            "url":     ilan_url,
        })

    # ── Strateji 2: /ilan/ içeren tüm linkler (tablo bulunamazsa) ───────────
    if not listings:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/ilan/" not in href or "/kategori/" in href or "/tum-ilanlar" in href:
                continue
            title = a.get_text(strip=True)
            if len(title) < 10:
                continue
            full_url = href if href.startswith("http") else BASE_URL + href
            listings.append({
                "kurum": "", "title": title,
                "ilan_no": href.split("/")[-1],
                "sehir": "", "url": full_url,
            })

    print(f"[Sayfa {page}] {len(listings)} ilan bulundu.")
    return listings


def format_notification(ilan):
    return (
        f"🎓 <b>Yeni Akademik İlan!</b>\n\n"
        f"🏛️ <b>{ilan['kurum']}</b>\n"
        f"📌 {ilan['title']}\n"
        f"📍 {ilan['sehir']}\n"
        f"🔢 İlan No: <code>{ilan['ilan_no']}</code>\n"
        f"🔗 <a href=\"{ilan['url']}\">İlana Git →</a>\n\n"
        f"🏷️ #MolekulerBiyoloji #AkademikIlan #ilangovtr"
    )

# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Başlıyor...")
    seen_ids = load_seen_ids()
    driver   = get_driver()
    all_listings = []

    try:
        for page in range(1, 20):   # En fazla 7 sayfa (112 ilan / ~20 = 6 sayfa)
            page_items = fetch_page(driver, page)
            if not page_items:
                print(f"[Sayfa {page}] Boş, duruyorum.")
                break
            all_listings.extend(page_items)
            time.sleep(2)
    finally:
        driver.quit()

    print(f"\nToplam {len(all_listings)} ilan tarandı.")

    new_count = 0
    for ilan in all_listings:
        combined = f"{ilan['title']} {ilan['kurum']}"
        if not matches_keywords(combined):
            continue

        ilan_id = make_id(ilan["ilan_no"], ilan["title"])
        if ilan_id in seen_ids:
            print(f"  [Görüldü] {ilan['title'][:60]}")
            continue

        print(f"  [YENİ] {ilan['title'][:60]}")
        try:
            send_telegram(format_notification(ilan))
            seen_ids.add(ilan_id)
            new_count += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [Hata] {e}")

        if TEST_MODE and new_count >= 3:
            print("TEST: 3 ilan gönderildi, duruyorum.")
            break

    save_seen_ids(seen_ids)

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ozet = (
        f"🔍 <b>Tarama Tamamlandı</b>\n🕐 {now}\n"
        f"📊 {len(all_listings)} ilan tarandı\n"
        + (f"🆕 <b>{new_count} yeni ilan bildirildi!</b>" if new_count
           else "✅ Yeni Mol. Biyoloji & Genetik ilanı yok.")
    )
    send_telegram(ozet)
    print(f"Bitti. {new_count} yeni ilan.")

if __name__ == "__main__":
    main()
