#!/usr/bin/env python3
import os, requests, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15
    )
    time.sleep(0.5)

def get_driver():
    opts = Options()
    for a in ["--headless","--no-sandbox","--disable-dev-shm-usage","--disable-gpu","--window-size=1920,1080"]:
        opts.add_argument(a)
    return webdriver.Chrome(options=opts)

def main():
    driver = get_driver()
    try:
        driver.get("https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel")
        time.sleep(10)  # Uzun bekle
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # 1) Kaç tane tr/td var?
        trs = soup.find_all("tr")
        tds = soup.find_all("td")
        send(f"📊 TR sayısı: {len(trs)}\nTD sayısı: {len(tds)}\nHTML uzunluğu: {len(html)}")

        # 2) Tüm class'lar
        all_classes = set()
        for tag in soup.find_all(class_=True):
            for cls in tag.get("class", []):
                all_classes.add(cls)
        send(f"🏷️ CLASS'LAR:\n<code>{', '.join(sorted(all_classes))}</code>")

        # 3) Sayfadaki tüm text (ilk 3000 kar)
        body_text = soup.get_text(separator="\n", strip=True)
        send(f"📄 SAYFA METNİ (ilk 3000):\n<code>{body_text[:3000]}</code>")

        # 4) HTML'nin 6000-9000. karakterleri (ilanların olduğu bölge)
        chunk = html[6000:10000].replace("<","&lt;").replace(">","&gt;")
        send(f"🧬 HTML 6000-10000:\n<code>{chunk[:3000]}</code>")

        # 5) HTML'nin 10000-13000. karakterleri
        chunk2 = html[10000:14000].replace("<","&lt;").replace(">","&gt;")
        send(f"🧬 HTML 10000-14000:\n<code>{chunk2[:3000]}</code>")

    finally:
        driver.quit()

    # 6) Resmi Gazete de kontrol et
    import urllib3
    urllib3.disable_warnings()
    url = "https://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/05/20260520-4.htm"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
        send(f"📰 RG Status: {resp.status_code}\nHTML uzunluğu: {len(resp.text)}\n\nİlk 2000 kar:\n<code>{resp.text[:2000].replace('<','&lt;').replace('>','&gt;')}</code>")
    except Exception as e:
        send(f"📰 RG Hata: {e}")

if __name__ == "__main__":
    main()
