#!/usr/bin/env python3
import os, requests, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15
    )

def main():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=opts)

    try:
        url = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"
        driver.get(url)

        # 10 saniye bekle — JS tam yüklensin
        time.sleep(10)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # 1) Tüm class'lar
        all_classes = set()
        for tag in soup.find_all(class_=True):
            for cls in tag.get("class", []):
                all_classes.add(cls)
        send(f"🏷️ CLASS'LAR:\n<code>{', '.join(sorted(all_classes)[:60])}</code>")

        # 2) Tüm linkler
        links = soup.find_all("a", href=True)
        link_sample = "\n".join(
            f"{a.get_text(strip=True)[:40]} → {a['href'][:60]}"
            for a in links[:20]
        )
        send(f"🔗 İLK 20 LİNK ({len(links)} toplam):\n<code>{link_sample}</code>")

        # 3) HTML gövdesi (ilk 2000 kar)
        body = soup.find("body")
        body_text = body.get_text(separator="\n", strip=True)[:2000] if body else "YOK"
        send(f"📄 SAYFA METNİ:\n<code>{body_text}</code>")

        # 4) Ham HTML (orta kısım — JS yüklendikten sonraki içerik)
        mid = html[3000:6000].replace("<","&lt;").replace(">","&gt;")
        send(f"🧬 HAM HTML (3000-6000):\n<code>{mid[:3000]}</code>")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
