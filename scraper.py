#!/usr/bin/env python3
"""
GitHub Actions'tan hangi sitelere erişilebildiğini test eder
"""
import os, requests, time
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg[:4000],
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=15
    )
    time.sleep(0.5)

SITES = [
    ("memurlar.net devlet akademik",   "https://ilan.memurlar.net/kategori/akademik-ilanlar-devlet/"),
    ("memurlar.net vakıf akademik",    "https://ilan.memurlar.net/kategori/akademik-ilanlar-vakif/"),
    ("memurlar.net ana",               "https://ilan.memurlar.net/"),
    ("akademikkadro.com",              "https://www.akademikkadro.com/"),
    ("akademikkadro.com ilanlar",      "https://www.akademikkadro.com/ilanlar/"),
    ("akademikkadro.net",              "https://www.akademikkadro.net/"),
    ("yok.gov.tr akademik",            "https://www.yok.gov.tr/akademik-personel"),
    ("universiteilan.com",             "https://www.universiteilan.com/"),
    ("ogretimuyesi.com",               "https://www.ogretimuyesi.com/"),
    ("kariyer.net akademik",           "https://www.kariyer.net/is-ilanlari/?q=akademik+kadro"),
    ("yosilanlar.com",                 "https://yosilanlar.com/"),
    ("memurlar.net haber akademik",    "https://www.memurlar.net/haber/kategori/akademik-ilan/"),
]

def main():
    send("🔍 Site erişim testi başlıyor...")
    results = []

    for name, url in SITES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12, verify=False, allow_redirects=True)
            size = len(r.text)
            if r.status_code == 200 and size > 1000:
                soup = BeautifulSoup(r.text, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                results.append(f"✅ <b>{name}</b>\n   {url}\n   {size} kar | İçerik: {text[:150]}")
            else:
                results.append(f"❌ {name} → HTTP {r.status_code} ({size} kar)")
        except Exception as e:
            results.append(f"⚠️ {name} → HATA: {str(e)[:60]}")
        time.sleep(0.5)

    # Gruplar halinde gönder
    chunk = []
    for r in results:
        chunk.append(r)
        if len(chunk) >= 4:
            send("\n\n".join(chunk))
            chunk = []
            time.sleep(1)
    if chunk:
        send("\n\n".join(chunk))

    accessible = [r for r in results if r.startswith("✅")]
    send(f"📊 Sonuç: {len(accessible)}/{len(SITES)} site erişilebilir")

if __name__ == "__main__":
    main()
