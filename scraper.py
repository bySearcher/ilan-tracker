#!/usr/bin/env python3
"""
Akademik Kadro Takip Botu
Kaynak 1: ilan.gov.tr  (Selenium - JS ile yükleniyor)
Kaynak 2: resmigazete.gov.tr  (requests - HTM/statik)
Anahtar kelime: Moleküler Biyoloji ve Genetik
"""

import os, json, hashlib, time, requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

# ── Ayarlar ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KEYWORDS = [
    "moleküler biyoloji",
    "moleküler biyoloji ve genetik",
    "molecular biology",
    "mbg",
    "genetik",
]

ILAN_BASE      = "https://www.ilan.gov.tr"
ILAN_URL       = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"
RG_BASE        = "https://www.resmigazete.gov.tr"
SEEN_FILE      = "data/seen_ids.json"
TEST_MODE      = True   # True = tüm ilanları eşleştir (test için)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# ── Yardımcı ─────────────────────────────────────────────────────────────────

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen_ids(ids):
    os.makedirs("data", exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

def make_id(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()

def matches(text):
    if TEST_MODE:
        return True
    return any(kw in text.lower() for kw in KEYWORDS)

def send_telegram(msg):
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
              "parse_mode": "HTML", "disable_web_page_preview": False},
        timeout=15
    )
    resp.raise_for_status()
    print(f"  [Telegram] {msg[:80]}...")

def get_driver():
    opts = Options()
    for arg in ["--headless","--no-sandbox","--disable-dev-shm-usage",
                "--disable-gpu","--window-size=1920,1080","--lang=tr-TR"]:
        opts.add_argument(arg)
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")
    return webdriver.Chrome(options=opts)

# ── KAYNAK 1: ilan.gov.tr ────────────────────────────────────────────────────

def fetch_ilan_page(driver, page=1):
    url = f"{ILAN_URL}?page={page}" if page > 1 else ILAN_URL
    print(f"  [ilan.gov.tr Sayfa {page}] {url}")
    driver.get(url)
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

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        texts  = [c.get_text(strip=True) for c in cells]
        kurum  = texts[0] if len(texts) > 0 else ""
        baslik = texts[1] if len(texts) > 1 else ""
        ilan_no= texts[2] if len(texts) > 2 else ""
        sehir  = texts[3] if len(texts) > 3 else ""
        if not baslik or not ilan_no:
            continue
        link_el = row.find("a", href=True)
        if link_el:
            href = link_el["href"]
            ilan_url = href if href.startswith("http") else ILAN_BASE + href
        else:
            ilan_url = f"{ILAN_BASE}/ilan/{ilan_no.lower()}"
        listings.append({
            "source": "ilan.gov.tr",
            "kurum": kurum, "title": baslik,
            "ilan_no": ilan_no, "sehir": sehir, "url": ilan_url,
        })

    print(f"  → {len(listings)} ilan")
    return listings

def scrape_ilan(driver):
    print("\n[KAYNAK 1] ilan.gov.tr taranıyor...")
    all_items = []
    for page in range(1, 8):
        items = fetch_ilan_page(driver, page)
        if not items:
            break
        all_items.extend(items)
        time.sleep(2)
    print(f"  Toplam: {len(all_items)} ilan")
    return all_items

# ── KAYNAK 2: resmigazete.gov.tr ─────────────────────────────────────────────

def rg_date_urls(days_back=3):
    """Son N günün Resmi Gazete 'Çeşitli İlanlar' URL'lerini üret."""
    urls = []
    today = datetime.now()
    for i in range(days_back):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y%m%d")
        year  = d.strftime("%Y")
        month = d.strftime("%m")
        # Çeşitli İlanlar = bölüm 4
        urls.append({
            "url": f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{month}/{date_str}-4.htm",
            "tarih": d.strftime("%d.%m.%Y"),
        })
    return urls

def scrape_resmi_gazete():
    print("\n[KAYNAK 2] resmigazete.gov.tr taranıyor...")
    all_items = []

    for entry in rg_date_urls(days_back=3):
        url   = entry["url"]
        tarih = entry["tarih"]
        print(f"  [{tarih}] {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if resp.status_code == 404:
                print(f"  → O gün gazete yok (404)")
                continue
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator="\n")

            # Sayfayı satırlara böl, üniversite/akademik satırlarını bul
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            found_sections = []
            for i, line in enumerate(lines):
                if any(kw in line.lower() for kw in
                       ["üniversitesi", "rektörlüğünden", "rektörlüğü",
                        "öğretim üyesi", "öğretim görevlisi", "araştırma görevlisi",
                        "akademik"]):
                    # Etraf bağlamı al
                    context = " ".join(lines[max(0,i-1):i+5])
                    if matches(context) or (TEST_MODE and len(found_sections) < 2):
                        found_sections.append({
                            "source": "Resmi Gazete",
                            "kurum": line[:150],
                            "title": " ".join(lines[i:i+3])[:200],
                            "ilan_no": f"RG-{tarih}-{i}",
                            "sehir": "",
                            "url": url,
                            "tarih": tarih,
                        })

            print(f"  → {len(found_sections)} eşleşen bölüm bulundu")
            all_items.extend(found_sections)
            time.sleep(1)

        except Exception as e:
            print(f"  → Hata: {e}")

    print(f"  Toplam: {len(all_items)} Resmi Gazete ilanı")
    return all_items

# ── Bildirim Formatı ─────────────────────────────────────────────────────────

def format_ilan(item):
    kaynak = item.get("source", "")
    tarih  = item.get("tarih", "")
    tarih_str = f"\n📅 Tarih: {tarih}" if tarih else ""
    return (
        f"🎓 <b>Yeni Akademik İlan!</b>\n"
        f"📰 <i>Kaynak: {kaynak}</i>{tarih_str}\n\n"
        f"🏛️ <b>{item.get('kurum','')[:150]}</b>\n"
        f"📌 {item.get('title','')[:200]}\n"
        + (f"📍 {item['sehir']}\n" if item.get('sehir') else "")
        + (f"🔢 İlan No: <code>{item['ilan_no']}</code>\n" if item.get('ilan_no') else "")
        + f"🔗 <a href=\"{item['url']}\">İlana Git →</a>\n\n"
        f"🏷️ #MolekulerBiyoloji #AkademikIlan"
    )

# ── Ana Akış ─────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Başlıyor...")
    seen_ids = load_seen_ids()
    driver   = get_driver()

    try:
        kaynak1 = scrape_ilan(driver)
    finally:
        driver.quit()

    kaynak2  = scrape_resmi_gazete()
    all_items = kaynak1 + kaynak2

    print(f"\nToplam tarama: {len(all_items)} ilan (ilan.gov.tr: {len(kaynak1)}, RG: {len(kaynak2)})")

    new_count = 0
    for item in all_items:
        combined = f"{item.get('title','')} {item.get('kurum','')} {item.get('title','')}"
        if not matches(combined):
            continue

        uid = make_id(item.get("ilan_no",""), item.get("title",""), item.get("source",""))
        if uid in seen_ids:
            print(f"  [Görüldü] {item['title'][:60]}")
            continue

        print(f"  [YENİ ✓] {item['title'][:60]}")
        try:
            send_telegram(format_ilan(item))
            seen_ids.add(uid)
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
        f"🔍 <b>Tarama Tamamlandı</b>\n"
        f"🕐 {now}\n"
        f"📊 ilan.gov.tr: {len(kaynak1)} ilan\n"
        f"📰 Resmi Gazete: {len(kaynak2)} bölüm\n"
        + (f"🆕 <b>{new_count} yeni ilan bildirildi!</b>"
           if new_count else "✅ Yeni Mol. Biyoloji & Genetik ilanı yok.")
    )
    send_telegram(ozet)
    print(f"Bitti. {new_count} yeni ilan.")

if __name__ == "__main__":
    main()
