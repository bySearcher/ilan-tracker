#!/usr/bin/env python3
"""
Resmi Gazete erişim testi - GitHub Actions'tan çalışır
"""
import os, requests, time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
RG_BASE = "https://www.resmigazete.gov.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.resmigazete.gov.tr/",
    "Connection": "keep-alive",
}

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15
    ).raise_for_status()
    time.sleep(0.5)

def main():
    send("🔍 Resmi Gazete erişim testi başlıyor...")

    # 1) Ana sayfaya bağlanabilir miyiz?
    try:
        r = requests.get(RG_BASE, headers=HEADERS, timeout=15, verify=False)
        send(f"Ana sayfa: <b>HTTP {r.status_code}</b>\n"
             f"Yanıt boyutu: {len(r.text)} karakter\n"
             f"İlk 200 kar:\n<code>{r.text[:200]}</code>")
    except Exception as e:
        send(f"❌ Ana sayfa HATA: {e}")
        return

    if r.status_code != 200:
        send("❌ Ana sayfaya erişilemiyor. Engel var.")
        return

    # 2) Son 14 günün ilanlarını dene
    send("✅ Ana sayfaya erişildi! Şimdi ilan sayfaları deneniyor...")
    today = datetime.now()

    for i in range(14):
        d = today - timedelta(days=i)
        ds    = d.strftime("%Y%m%d")
        year  = d.strftime("%Y")
        mon   = d.strftime("%m")
        tarih = d.strftime("%d.%m.%Y (%A)")

        # Tüm olası bölüm numaraları
        for bolum in [4, 3, 5, 2]:
            url = f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{mon}/{ds}-{bolum}.htm"
            try:
                r2 = requests.get(url, headers=HEADERS, timeout=10, verify=False)
                if r2.status_code == 200 and len(r2.text) > 1000:
                    soup = BeautifulSoup(r2.text, "html.parser")
                    text = soup.get_text(separator=" ", strip=True)
                    send(f"✅ <b>{tarih}</b> Bölüm-{bolum} BULUNDU!\n"
                         f"🔗 {url}\n"
                         f"Boyut: {len(r2.text)} kar\n\n"
                         f"İlk 400 kar:\n<code>{text[:400]}</code>")
                    time.sleep(0.5)
                    break
            except Exception as e:
                pass
        time.sleep(0.3)

if __name__ == "__main__":
    main()
