#!/usr/bin/env python3
"""
TAM TEST MODU
- ilan.gov.tr: 1. sayfadaki TÜM ilanları gönderir
- Resmi Gazete: bugünkü TÜM akademik ilanları gönderir
- Keyword filtresi YOK, seen_ids kontrolü YOK
"""

import os, requests, time
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
    print(f"  [Telegram] {msg[:80]}")
    time.sleep(0.5)

def get_driver():
    opts = Options()
    for a in ["--headless","--no-sandbox","--disable-dev-shm-usage","--disable-gpu","--window-size=1920,1080"]:
        opts.add_argument(a)
    return webdriver.Chrome(options=opts)

# ── KAYNAK 1: ilan.gov.tr sayfa 1 ────────────────────────────────────────────

def scrape_ilan(driver):
    print("\n[ilan.gov.tr] Sayfa 1 yükleniyor...")
    driver.get(ILAN_URL)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//*[contains(text(),'Toplam') and contains(text(),'ilan')]"))
        )
    except Exception:
        pass
    time.sleep(4)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        texts  = [c.get_text(strip=True) for c in cells]
        kurum  = texts[0] if len(texts) > 0 else ""
        baslik = texts[1] if len(texts) > 1 else ""
        ilan_no= texts[2] if len(texts) > 2 else ""
        sehir  = texts[3] if len(texts) > 3 else ""
        if not baslik:
            continue
        link_el = row.find("a", href=True)
        href = link_el["href"] if link_el else f"/ilan/{ilan_no.lower()}"
        url  = href if href.startswith("http") else ILAN_BASE + href
        items.append({"kurum": kurum, "baslik": baslik,
                      "ilan_no": ilan_no, "sehir": sehir, "url": url})

    print(f"  {len(items)} ilan bulundu.")
    return items

# ── KAYNAK 2: Resmi Gazete bugün ─────────────────────────────────────────────

def scrape_rg_bugun():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    year  = today.strftime("%Y")
    month = today.strftime("%m")
    tarih_goster = today.strftime("%d.%m.%Y")

    # Resmi Gazete Çeşitli İlanlar sayfası (bölüm -4)
    url = f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{month}/{date_str}-4.htm"
    print(f"\n[Resmi Gazete] {tarih_goster} → {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code == 404:
            # Bugün henüz yayınlanmadıysa dün de dene
            yesterday = today.replace(day=today.day-1)
            date_str2 = yesterday.strftime("%Y%m%d")
            month2    = yesterday.strftime("%m")
            url = f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{month2}/{date_str2}-4.htm"
            tarih_goster = yesterday.strftime("%d.%m.%Y")
            print(f"  Bugün yok, dün deneniyor: {tarih_goster}")
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)

        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 10]

        # Akademik ilan bölümlerini bul
        akademik_keywords = [
            "üniversitesi", "rektörlüğünden", "rektörlüğü",
            "öğretim üyesi", "öğretim görevlisi", "araştırma görevlisi",
            "akademik", "profesör", "doçent", "doktor öğretim"
        ]

        sections = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if any(kw in line.lower() for kw in akademik_keywords):
                # Bu satır ve sonraki 4 satırı birleştir
                block = "\n".join(lines[i:i+5])
                sections.append({
                    "baslik": line[:200],
                    "detay": block[:500],
                    "url": url,
                    "tarih": tarih_goster,
                })
                i += 5  # Çakışmayı önlemek için atla
            else:
                i += 1

        print(f"  {len(sections)} akademik bölüm bulundu.")
        return sections, tarih_goster, url

    except Exception as e:
        print(f"  Hata: {e}")
        return [], tarih_goster, url

# ── Ana Akış ─────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] TAM TEST başlıyor...")

    driver = get_driver()
    try:
        ilan_items = scrape_ilan(driver)
    finally:
        driver.quit()

    rg_items, rg_tarih, rg_url = scrape_rg_bugun()

    # ── ilan.gov.tr bildirimleri ──────────────────────────────────────────────
    send(
        f"📋 <b>ilan.gov.tr — Sayfa 1 Sonuçları</b>\n"
        f"Toplam <b>{len(ilan_items)}</b> ilan bulundu. Teker teker gönderiliyor..."
    )
    time.sleep(1)

    for idx, item in enumerate(ilan_items, 1):
        msg = (
            f"[{idx}/{len(ilan_items)}] 🏛 ilan.gov.tr\n\n"
            f"<b>{item['kurum']}</b>\n"
            f"📌 {item['baslik']}\n"
            f"📍 {item['sehir']}  |  🔢 {item['ilan_no']}\n"
            f"🔗 <a href=\"{item['url']}\">İlana Git</a>"
        )
        try:
            send(msg)
        except Exception as e:
            print(f"  Hata (ilan {idx}): {e}")
            time.sleep(3)

    # ── Resmi Gazete bildirimleri ─────────────────────────────────────────────
    time.sleep(2)
    send(
        f"📰 <b>Resmi Gazete — {rg_tarih} Akademik İlanlar</b>\n"
        f"Toplam <b>{len(rg_items)}</b> akademik bölüm bulundu.\n"
        f"🔗 <a href=\"{rg_url}\">Sayfayı Gör</a>"
    )
    time.sleep(1)

    for idx, item in enumerate(rg_items, 1):
        msg = (
            f"[{idx}/{len(rg_items)}] 📰 Resmi Gazete ({item['tarih']})\n\n"
            f"<b>{item['baslik'][:150]}</b>\n\n"
            f"<i>{item['detay'][:300]}</i>\n\n"
            f"🔗 <a href=\"{item['url']}\">Tam İlan</a>"
        )
        try:
            send(msg)
        except Exception as e:
            print(f"  Hata (RG {idx}): {e}")
            time.sleep(3)

    # ── Özet ─────────────────────────────────────────────────────────────────
    send(
        f"✅ <b>TAM TEST Tamamlandı</b>\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📊 ilan.gov.tr sayfa 1: <b>{len(ilan_items)}</b> ilan\n"
        f"📰 Resmi Gazete ({rg_tarih}): <b>{len(rg_items)}</b> akademik bölüm"
    )
    print("Bitti.")

if __name__ == "__main__":
    main()
