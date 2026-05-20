#!/usr/bin/env python3
"""
Akademik Kadro Takip Botu - v5
Kaynak 1: ilan.gov.tr        (Selenium)
Kaynak 2: ilan.memurlar.net  (requests - Resmi Gazete ilanlarını topluyor)
Kaynak 3: ilan.gov.tr/kategori/73 Akademik Personel Alımları (ayrı kategori)
"""

import os, json, hashlib, time, re, requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KEYWORDS = [
    "moleküler biyoloji",
    "moleküler biyoloji ve genetik",
    "molecular biology",
    "mbg",
    "genetik",
]

ILAN_BASE  = "https://www.ilan.gov.tr"
SEEN_FILE  = "data/seen_ids.json"
TEST_MODE  = True

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

ILAN_NO_PATTERN = re.compile(r'^(YOK|DPB|RG|IK|SB)\d+$', re.IGNORECASE)
SEHIR_LIST = {
    "ADANA","ADIYAMAN","AFYONKARAHİSAR","AĞRI","AKSARAY","AMASYA","ANKARA",
    "ANTALYA","ARDAHAN","ARTVİN","AYDIN","BALIKESİR","BARTIN","BATMAN",
    "BAYBURT","BİLECİK","BİNGÖL","BİTLİS","BOLU","BURDUR","BURSA",
    "ÇANAKKALE","ÇANKIRI","ÇORUM","DENİZLİ","DİYARBAKIR","DÜZCE","EDİRNE",
    "ELAZIĞ","ERZİNCAN","ERZURUM","ESKİŞEHİR","GAZİANTEP","GİRESUN",
    "GÜMÜŞHANE","HAKKARİ","HATAY","IĞDIR","ISPARTA","İSTANBUL","İZMİR",
    "KAHRAMANMARAŞ","KARABÜK","KARAMAN","KARS","KASTAMONU","KAYSERİ",
    "KIRIKKALE","KIRKLARELİ","KIRŞEHİR","KİLİS","KOCAELİ","KONYA","KÜTAHYA",
    "MALATYA","MANİSA","MARDİN","MERSİN","MUĞLA","MUŞ","NEVŞEHİR","NİĞDE",
    "ORDU","OSMANİYE","RİZE","SAKARYA","SAMSUN","SİİRT","SİNOP","SİVAS",
    "ŞANLIURFA","ŞIRNAK","TEKİRDAĞ","TOKAT","TRABZON","TUNCELİ","UŞAK",
    "VAN","YALOVA","YOZGAT","ZONGULDAK"
}

# ── Yardımcılar ───────────────────────────────────────────────────────────────

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
    return hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()

def matches(text):
    if TEST_MODE:
        return True
    return any(kw in text.lower() for kw in KEYWORDS)

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
              "parse_mode": "HTML", "disable_web_page_preview": False},
        timeout=15
    ).raise_for_status()
    time.sleep(0.5)

def get_driver():
    opts = Options()
    for a in ["--headless","--no-sandbox","--disable-dev-shm-usage",
              "--disable-gpu","--window-size=1920,1080"]:
        opts.add_argument(a)
    return webdriver.Chrome(options=opts)

# ── KAYNAK 1 & 3: ilan.gov.tr (Selenium, metin parse) ────────────────────────

def parse_text_to_ilanlar(text, source_url):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    start = 0
    for i, l in enumerate(lines):
        if "Toplam" in l and "ilan" in l:
            start = i + 5
            break
    end = len(lines)
    for i, l in enumerate(lines[start:], start):
        if "Önceki" in l:
            end = i
            break

    chunk = lines[start:end]
    items = []
    i = 0
    while i < len(chunk) - 2:
        kurum   = chunk[i]
        baslik  = chunk[i+1] if i+1 < len(chunk) else ""
        ilan_no = chunk[i+2] if i+2 < len(chunk) else ""
        sehir   = chunk[i+3] if i+3 < len(chunk) else ""

        if ILAN_NO_PATTERN.match(ilan_no):
            if sehir.upper() not in SEHIR_LIST:
                sehir = ""
                step = 3
            else:
                step = 4
            items.append({
                "source": "ilan.gov.tr",
                "kurum":  kurum,
                "baslik": baslik,
                "ilan_no": ilan_no,
                "sehir":  sehir,
                "url":    f"{ILAN_BASE}/ilan/{ilan_no.lower()}",
            })
            i += step
        else:
            i += 1
    return items

def scrape_ilan_url(driver, url, label):
    print(f"  [{label}] {url}")
    driver.get(url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//*[contains(text(),'Toplam') and contains(text(),'ilan')]"))
        )
    except Exception:
        pass
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    items = parse_text_to_ilanlar(text, url)
    print(f"  → {len(items)} ilan")
    return items

def scrape_ilangovtr(driver):
    print("\n[KAYNAK 1+3] ilan.gov.tr taranıyor...")
    all_items = []
    # Kategori 8: Kamu-Akademik Personel
    for page in range(1, 11):
        url = f"{ILAN_BASE}/ilan/kategori/8/kamu-akademik-personel" + (f"?page={page}" if page > 1 else "")
        items = scrape_ilan_url(driver, url, f"Kategori-8 Sayfa-{page}")
        if not items:
            break
        all_items.extend(items)
        time.sleep(2)
    # Kategori 73: Akademik Personel Alımları (ayrı kategori)
    for page in range(1, 6):
        url = f"{ILAN_BASE}/ilan/kategori/73/akademik-personel-alimlari" + (f"?page={page}" if page > 1 else "")
        items = scrape_ilan_url(driver, url, f"Kategori-73 Sayfa-{page}")
        if not items:
            break
        all_items.extend(items)
        time.sleep(2)
    # Tekrarları kaldır
    seen = set()
    unique = []
    for it in all_items:
        if it["ilan_no"] not in seen:
            seen.add(it["ilan_no"])
            unique.append(it)
    print(f"  Toplam: {len(unique)} tekrarsız ilan")
    return unique

# ── KAYNAK 2: ilan.memurlar.net (Resmi Gazete ilanlarını topluyor) ────────────

def scrape_memurlar():
    print("\n[KAYNAK 2] ilan.memurlar.net taranıyor...")
    items = []

    # Devlet akademik ilanları
    urls = [
        ("https://ilan.memurlar.net/kategori/akademik-ilanlar-devlet/", "Devlet"),
        ("https://ilan.memurlar.net/kategori/akademik-ilanlar-vakif/",  "Vakıf"),
    ]

    for url, label in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # memurlar.net ilan kartları
            cards = soup.select("div.ilan-item, article.ilan, div.list-item, .ilan-listesi li, table tr")

            # Fallback: tüm linkleri tara
            if not cards:
                links = soup.find_all("a", href=True)
                for a in links:
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    if ("ilan" in href.lower() or "akademik" in href.lower()) and len(title) > 15:
                        full_url = href if href.startswith("http") else "https://ilan.memurlar.net" + href
                        items.append({
                            "source":  f"memurlar.net ({label})",
                            "kurum":   "",
                            "baslik":  title[:200],
                            "ilan_no": make_id(title, href)[:12],
                            "sehir":   "",
                            "url":     full_url,
                        })
            else:
                for card in cards:
                    link = card.find("a", href=True)
                    if not link:
                        continue
                    title = card.get_text(strip=True)[:200]
                    href  = link["href"]
                    full_url = href if href.startswith("http") else "https://ilan.memurlar.net" + href
                    if len(title) > 15:
                        items.append({
                            "source":  f"memurlar.net ({label})",
                            "kurum":   "",
                            "baslik":  title,
                            "ilan_no": make_id(title, href)[:12],
                            "sehir":   "",
                            "url":     full_url,
                        })

            print(f"  [{label}] {len([i for i in items if label in i['source']])} ilan")
            time.sleep(1)

        except Exception as e:
            print(f"  [{label}] Hata: {e}")

    print(f"  Toplam: {len(items)} ilan")
    return items

# ── Bildirim ──────────────────────────────────────────────────────────────────

def format_bildirim(item):
    kaynak = item.get("source", "")
    kurum  = item.get("kurum", "")
    sehir  = item.get("sehir", "")
    return (
        f"🎓 <b>Yeni Akademik İlan!</b>\n"
        f"📰 <i>{kaynak}</i>\n\n"
        + (f"🏛️ <b>{kurum}</b>\n" if kurum else "")
        + f"📌 {item['baslik'][:200]}\n"
        + (f"📍 {sehir}\n" if sehir else "")
        + f"🔗 <a href=\"{item['url']}\">İlana Git →</a>\n\n"
        f"🏷️ #MolekulerBiyoloji #AkademikIlan"
    )

# ── Ana Akış ──────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Başlıyor...")
    seen_ids = load_seen_ids()

    driver = get_driver()
    try:
        k1 = scrape_ilangovtr(driver)
    finally:
        driver.quit()

    k2 = scrape_memurlar()
    all_items = k1 + k2

    print(f"\nToplam: {len(all_items)} ilan tarandı")

    new_count = 0
    for item in all_items:
        combined = f"{item['baslik']} {item.get('kurum','')}"
        if not matches(combined):
            continue

        uid = make_id(item.get("ilan_no",""), item["baslik"], item["source"])
        if uid in seen_ids:
            print(f"  [Görüldü] {item['baslik'][:60]}")
            continue

        print(f"  [YENİ ✓] {item['baslik'][:60]}")
        try:
            send(format_bildirim(item))
            seen_ids.add(uid)
            new_count += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [Hata] {e}")

        if TEST_MODE and new_count >= 3:
            break

    save_seen_ids(seen_ids)

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ozet = (
        f"🔍 <b>Tarama Tamamlandı</b>\n🕐 {now}\n\n"
        f"📊 ilan.gov.tr: <b>{len(k1)}</b> ilan\n"
        f"📰 memurlar.net: <b>{len(k2)}</b> ilan\n"
        + (f"🆕 <b>{new_count} yeni ilan bildirildi!</b>"
           if new_count else "✅ Yeni Mol. Biyoloji & Genetik ilanı yok.")
    )
    send(ozet)
    print(f"Bitti. {new_count} yeni ilan.")

if __name__ == "__main__":
    main()
