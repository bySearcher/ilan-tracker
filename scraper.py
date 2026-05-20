#!/usr/bin/env python3
"""
DEBUG versiyonu - HTML yapısını görmek için
"""

import os
import requests
import urllib3
urllib3.disable_warnings()

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()

def main():
    url = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        status = resp.status_code
        html = resp.text
        
        # HTML'nin ilk 2000 karakterini Telegram'a gönder (yapıyı anlamak için)
        preview = html[:2000].replace("<", "&lt;").replace(">", "&gt;")
        
        msg = (
            f"🔍 <b>DEBUG Raporu</b>\n\n"
            f"📡 Status: {status}\n"
            f"📄 HTML uzunluğu: {len(html)} karakter\n\n"
            f"<b>İlk 1500 karakter:</b>\n"
            f"<code>{preview[:1500]}</code>"
        )
        send_telegram(msg)
        
        # Ayrıca ilan linklerini bul ve gönder
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Tüm linkleri tara
        all_links = soup.find_all("a", href=True)
        ilan_links = [a for a in all_links if "/ilan/" in a.get("href", "")]
        
        link_text = "\n".join([
            f"• {a.get_text(strip=True)[:50]} → {a['href'][:80]}"
            for a in ilan_links[:10]
        ])
        
        msg2 = (
            f"🔗 <b>Bulunan İlan Linkleri ({len(ilan_links)} adet):</b>\n\n"
            f"{link_text if link_text else 'HİÇ LİNK BULUNAMADI'}"
        )
        send_telegram(msg2)
        
        # Tüm CSS class'larını listele
        all_classes = set()
        for tag in soup.find_all(class_=True):
            for cls in tag.get("class", []):
                all_classes.add(cls)
        
        class_list = ", ".join(sorted(all_classes)[:50])
        msg3 = f"🏷️ <b>HTML Class'ları:</b>\n<code>{class_list}</code>"
        send_telegram(msg3)
        
    except Exception as e:
        send_telegram(f"❌ <b>Hata:</b> {str(e)}")

if __name__ == "__main__":
    main()
