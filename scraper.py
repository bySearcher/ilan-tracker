#!/usr/bin/env python3
"""
Resmi Gazete debug + düzeltilmiş tarayıcı
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
}

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=15
    ).raise_for_status()
    time.sleep(0.8)

def try_url(url, label):
    """URL'yi dener, status ve içerik özeti döner."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        soup = BeautifulSoup(r.text, "html.parser") if r.status_code == 200 else None
        text = soup.get_text(separator=" ", strip=True)[:500] if soup else ""
        return r.status_code, text
    except Exception as e:
        return 0, str(e)

def main():
    today = datetime.now()
    send(f"🔍 Resmi Gazete URL taraması başlıyor — {today.strftime('%d.%m.%Y')}")

    # Son 7 günün olası Çeşitli İlanlar URL'lerini dene
    found_urls = []
    for i in range(7):
        d = today - timedelta(days=i)
        ds   = d.strftime("%Y%m%d")
        year = d.strftime("%Y")
        mon  = d.strftime("%m")
        tarih = d.strftime("%d.%m.%Y")

        # Çeşitli İlanlar bölümleri: -4 ana, bazen -4-1, -4-2 vb.
        candidates = [
            f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{mon}/{ds}-4.htm",
            f"{RG_BASE}/ilanlar/eskiilanlar/{year}/{mon}/{ds}-4-1.htm",
            f"{RG_BASE}/eskiler/{year}/{mon}/{ds}-2.htm",  # bazen burada
            f"{RG_BASE}/eskiler/{year}/{mon}/{ds}.htm",
        ]
        for url in candidates:
            status, text = try_url(url, tarih)
            if status == 200 and len(text) > 200:
                snippet = text[:300].replace("<","&lt;")
                send(f"✅ <b>{tarih}</b> — BULUNDU\n🔗 {url}\n\n<code>{snippet}</code>")
                found_urls.append((tarih, url, text))
                break
        else:
            send(f"❌ {tarih} — Tüm URL'ler 404/boş")

        time.sleep(0.5)

    # Bulunan URL'lerde akademik içerik ara
    akademik_kw = ["üniversitesi","rektörlüğünden","öğretim","araştırma görevlisi","akademik"]
    send(f"\n📊 {len(found_urls)} aktif URL bulundu. Akademik içerik aranıyor...")

    for tarih, url, text in found_urls:
        lines = [l.strip() for l in text.split() if l.strip()]
        # Akademik satırlar
        hits = [l for l in text.split("\n") if any(kw in l.lower() for kw in akademik_kw)]
        if hits:
            sample = "\n".join(hits[:10])
            send(f"🎓 <b>{tarih}</b> — {len(hits)} akademik satır\n🔗 {url}\n\n<code>{sample[:600]}</code>")
        else:
            send(f"ℹ️ {tarih} — Akademik içerik yok\n🔗 {url}")

if __name__ == "__main__":
    main()
