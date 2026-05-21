#!/usr/bin/env python3
"""
Akademik Kadro Takip Botu
Kaynak: ilan.gov.tr - Kamu Akademik Personel ilanları
Anahtar kelime: Moleküler Biyoloji ve Genetik
"""

import os, json, hashlib, time, re
import requests
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

BASE_URL  = "https://www.ilan.gov.tr"
LISTE_URL = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"
SEEN_FILE = "data/seen_ids.json"

ILAN_NO_RE = re.compile(r'^(YOK|DPB|RG|IK|SB)\d+$', re.IGNORECASE)
SEHIRLER = {
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

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(ids):
    os.makedirs("data", exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

def make_id(ilan_no, baslik):
    return hashlib.md5(f"{ilan_no}|{baslik}".encode()).hexdigest()

def eslesir(metin):
    return any(kw in metin.lower() for kw in KEYWORDS)

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=15,
    ).raise_for_status()
    time.sleep(0.5)

def get_driver():
    opts = Options()
    for arg in ["--headless", "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--window-size=1920,1080", "--lang=tr-TR"]:
        opts.add_argument(arg)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)

# ── Parse ─────────────────────────────────────────────────────────────────────

def parse_sayfa(page_text):
    """
    Sayfa metnini satır satır okur.
    Format (debug'dan doğrulandı):
      KURUM ADI
      İlan Başlığı
      YOK123456   ← ilan no (regex ile tespit)
      ŞEHİR
    """
    lines = [l.strip() for l in page_text.split("\n") if l.strip()]

    # "Toplam X ilan" + sütun başlıklarından sonrasını al
    start = 0
    for i, l in enumerate(lines):
        if "Toplam" in l and "ilan" in l:
            start = i + 5
            break

    # Sayfalama başlangıcından öncesini al
    end = len(lines)
    for i, l in enumerate(lines[start:], start):
        if "Önceki" in l:
            end = i
            break

    chunk = lines[start:end]
    ilanlar = []
    i = 0
    while i < len(chunk):
        ilan_no = chunk[i]
        if ILAN_NO_RE.match(ilan_no):
            # Geriye bak: 2 satır önce kurum, 1 satır önce başlık
            kurum  = chunk[i - 2] if i >= 2 else ""
            baslik = chunk[i - 1] if i >= 1 else ""
            # İleriye bak: 1 satır sonra şehir
            sehir  = chunk[i + 1] if i + 1 < len(chunk) and chunk[i+1].upper() in SEHIRLER else ""
            ilanlar.append({
                "kurum":   kurum,
                "baslik":  baslik,
                "ilan_no": ilan_no,
                "sehir":   sehir,
                "url":     f"{BASE_URL}/ilan/{ilan_no.lower()}",
            })
        i += 1

    return ilanlar

# ── Tarama ────────────────────────────────────────────────────────────────────

def sayfayi_tara(driver, page):
    url = LISTE_URL if page == 1 else f"{LISTE_URL}?page={page}"
    print(f"  [Sayfa {page}] {url}")
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
    ilanlar = parse_sayfa(text)
    print(f"  → {len(ilanlar)} ilan")
    return ilanlar

def tum_ilanlari_cek(driver):
    print("[ilan.gov.tr] Taranıyor...")
    hepsi = []
    for page in range(1, 11):   # max 10 sayfa (~100+ ilan)
        ilanlar = sayfayi_tara(driver, page)
        if not ilanlar:
            print(f"  Sayfa {page} boş, duruyorum.")
            break
        hepsi.extend(ilanlar)
        time.sleep(2)

    # Tekrar eden ilan_no'ları temizle
    goruldu = set()
    tekrarsiz = []
    for il in hepsi:
        if il["ilan_no"] not in goruldu:
            goruldu.add(il["ilan_no"])
            tekrarsiz.append(il)

    print(f"Toplam: {len(tekrarsiz)} tekrarsız ilan")
    return tekrarsiz

# ── Bildirim ──────────────────────────────────────────────────────────────────

def bildirim_metni(ilan):
    return (
        f"🎓 <b>Yeni Akademik İlan!</b>\n\n"
        f"🏛️ <b>{ilan['kurum']}</b>\n"
        f"📌 {ilan['baslik']}\n"
        f"📍 {ilan['sehir']}\n"
        f"🔢 İlan No: <code>{ilan['ilan_no']}</code>\n"
        f"🔗 <a href=\"{ilan['url']}\">İlana Git →</a>\n\n"
        f"🏷️ #MolekulerBiyoloji #AkademikIlan #ilangovtr"
    )

# ── Ana Akış ──────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Başlıyor...")
    seen = load_seen()
    driver = get_driver()

    try:
        ilanlar = tum_ilanlari_cek(driver)
    finally:
        driver.quit()

    yeni_sayisi = 0
    for ilan in ilanlar:
        combined = f"{ilan['baslik']} {ilan['kurum']}"
        if not eslesir(combined):
            continue

        uid = make_id(ilan["ilan_no"], ilan["baslik"])
        if uid in seen:
            print(f"  [Görüldü] {ilan['baslik'][:60]}")
            continue

        print(f"  [YENİ ✓] {ilan['baslik'][:60]}")
        try:
            send(bildirim_metni(ilan))
            seen.add(uid)
            yeni_sayisi += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [Hata] {e}")

    save_seen(seen)

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ozet = (
        f"🔍 <b>Tarama Tamamlandı</b>\n"
        f"🕐 {now}\n"
        f"📊 Taranan ilan: <b>{len(ilanlar)}</b>\n"
        + (f"🆕 <b>{yeni_sayisi} yeni ilan bildirildi!</b>"
           if yeni_sayisi else
           "✅ Yeni Moleküler Biyoloji & Genetik ilanı bulunamadı.")
    )
    send(ozet)
    print(f"Bitti. {yeni_sayisi} yeni ilan.")

if __name__ == "__main__":
    main()
