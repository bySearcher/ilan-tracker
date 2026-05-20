#!/usr/bin/env python3
"""
TAM TEST MODU - v4
Sayfa metnini satır satır parse eder.
İlanlar tr/td değil, düz metin bloğu olarak geliyor.
"""

import os, requests, time, re
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

ILAN_BASE = "https://www.ilan.gov.tr"
ILAN_URL  = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"
RG_BASE   = "https://www.resmigazete.gov.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=15
    ).raise_for_status()
    time.sleep(0.5)

def get_driver():
    opts = Options()
    for a in ["--headless","--no-sandbox","--disable-dev-shm-usage",
              "--disable-gpu","--window-size=1920,1080"]:
        opts.add_argument(a)
    return webdriver.Chrome(options=opts)

# ── ilan.gov.tr: metin tabanlı parse ─────────────────────────────────────────
# Sayfa metni şu formatta geliyor (debug'dan gördük):
#   KURUM ADI
#   İlan Başlığı
#   İLAN_NO
#   ŞEHİR
# Bu döngüyle 4'lü bloklar halinde okuyoruz.

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

def parse_ilanlar_from_text(text):
    """
    Sayfa metnini 4'lü bloklar halinde parse eder:
    Kurum → Başlık → İlan No → Şehir
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # "Toplam X ilan" dan sonrasını al, footer'dan önce kes
    start = 0
    for i, l in enumerate(lines):
        if "Toplam" in l and "ilan" in l:
            # Sütun başlıklarını atla (Kurum, Başlık, İlan Numarası, Şehir)
            start = i + 5
            break

    end = len(lines)
    for i, l in enumerate(lines):
        if "Önceki" in l or "sayfa" in l.lower() and "1 / " in "".join(lines[i:i+3]):
            end = i
            break

    chunk = lines[start:end]

    items = []
    i = 0
    while i < len(chunk) - 2:
        kurum  = chunk[i]
        baslik = chunk[i+1] if i+1 < len(chunk) else ""
        ilan_no= chunk[i+2] if i+2 < len(chunk) else ""
        sehir  = chunk[i+3] if i+3 < len(chunk) else ""

        # Doğrulama: ilan_no formatı YOK/DPB/... ile başlamalı
        if ILAN_NO_PATTERN.match(ilan_no):
            # Şehir doğrulama
            if sehir.upper() not in SEHIR_LIST:
                sehir = ""
                step = 3
            else:
                step = 4
            items.append({
                "kurum":   kurum,
                "baslik":  baslik,
                "ilan_no": ilan_no,
                "sehir":   sehir,
                "url":     f"{ILAN_BASE}/ilan/{ilan_no.lower()}",
            })
            i += step
        else:
            i += 1

    return items

def scrape_ilan_page(driver, page=1):
    url = f"{ILAN_URL}?page={page}" if page > 1 else ILAN_URL
    print(f"  [ilan.gov.tr Sayfa {page}]")
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
    items = parse_ilanlar_from_text(text)
    print(f"  → {len(items)} ilan")
    return items

def scrape_ilan(driver):
    print("\n[KAYNAK 1] ilan.gov.tr taranıyor...")
    all_items = []
    for page in range(1, 11):  # 10 sayfa = ~100+ ilan
        items = scrape_ilan_page(driver, page)
        if not items:
            print(f"  Sayfa {page} boş, duruyorum.")
            break
        all_items.extend(items)
        time.sleep(2)
    print(f"  Toplam: {len(all_items)} ilan")
    return all_items

# ── Resmi Gazete ──────────────────────────────────────────────────────────────

def scrape_rg_bugun():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    year, month = today.strftime("%Y"), today.strftime("%m")
    tarih_goster = today.strftime("%d.%m.%Y")
    url = f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{month}/{date_str}-4.htm"

    print(f"\n[KAYNAK 2] Resmi Gazete {tarih_goster}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code == 404:
            send(f"📰 Resmi Gazete bugün ({tarih_goster}) henüz yayınlanmadı.")
            return [], tarih_goster, url

        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 8]

        akademik_kw = [
            "üniversitesi", "rektörlüğünden", "rektörlüğü",
            "öğretim üyesi", "öğretim görevlisi", "araştırma görevlisi",
            "akademik", "profesör", "doçent", "doktor öğretim üyesi"
        ]

        sections = []
        seen = set()
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in akademik_kw):
                key = line[:80]
                if key in seen:
                    continue
                seen.add(key)
                detay = "\n".join(lines[i:i+6])
                sections.append({
                    "baslik": line[:200],
                    "detay":  detay[:500],
                    "url":    url,
                    "tarih":  tarih_goster,
                })

        print(f"  {len(sections)} akademik bölüm")
        return sections, tarih_goster, url

    except Exception as e:
        print(f"  Hata: {e}")
        return [], tarih_goster, url

# ── Ana Akış ──────────────────────────────────────────────────────────────────

def main():
    driver = get_driver()
    try:
        ilan_items = scrape_ilan(driver)
    finally:
        driver.quit()

    rg_result = scrape_rg_bugun()
    rg_items, rg_tarih, rg_url = rg_result if len(rg_result) == 3 else ([], "", "")

    # ── ilan.gov.tr bildirimleri ──────────────────────────────────────────────
    send(
        f"📋 <b>ilan.gov.tr Sonuçları</b>\n"
        f"Toplam <b>{len(ilan_items)}</b> ilan bulundu."
    )
    for idx, item in enumerate(ilan_items, 1):
        msg = (
            f"[{idx}/{len(ilan_items)}] 🏛 <b>ilan.gov.tr</b>\n\n"
            f"<b>{item['kurum']}</b>\n"
            f"📌 {item['baslik']}\n"
            f"📍 {item['sehir']}  🔢 {item['ilan_no']}\n"
            f"🔗 <a href=\"{item['url']}\">İlana Git</a>"
        )
        try:
            send(msg)
        except Exception as e:
            print(f"Hata {idx}: {e}")
            time.sleep(3)

    # ── Resmi Gazete bildirimleri ─────────────────────────────────────────────
    time.sleep(1)
    send(
        f"📰 <b>Resmi Gazete — {rg_tarih}</b>\n"
        f"Toplam <b>{len(rg_items)}</b> akademik bölüm\n"
        f"🔗 <a href=\"{rg_url}\">Sayfayı Gör</a>"
    )
    for idx, item in enumerate(rg_items, 1):
        msg = (
            f"[{idx}/{len(rg_items)}] 📰 <b>Resmi Gazete</b> ({item['tarih']})\n\n"
            f"<b>{item['baslik'][:150]}</b>\n\n"
            f"<i>{item['detay'][:300]}</i>\n\n"
            f"🔗 <a href=\"{item['url']}\">Tam İlan</a>"
        )
        try:
            send(msg)
        except Exception as e:
            print(f"RG Hata {idx}: {e}")
            time.sleep(3)

    send(
        f"✅ <b>Test Tamamlandı</b> — {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 ilan.gov.tr: <b>{len(ilan_items)}</b> ilan\n"
        f"📰 Resmi Gazete: <b>{len(rg_items)}</b> bölüm"
    )

if __name__ == "__main__":
    main()
