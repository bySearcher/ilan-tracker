#!/usr/bin/env python3
"""
ilan.gov.tr Akademik Kadro Takip Botu
Moleküler Biyoloji ve Genetik ilanlarını tarar, yeni ilanları Telegram'a bildirir.
"""

import os
import json
import hashlib
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup

# ── Ayarlar ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Takip edilecek anahtar kelimeler (küçük harfe çevrilip aranır)
KEYWORDS = [
    "moleküler biyoloji",
    "moleküler biyoloji ve genetik",
    "molecular biology",
    "mbg",
    "genetik",
]

# ilan.gov.tr Kamu Akademik Personel kategorisi
BASE_URL = "https://www.ilan.gov.tr"
SEARCH_URL = "https://www.ilan.gov.tr/ilan/kategori/8/kamu-akademik-personel"

# Daha önce görülen ilanların ID'leri bu dosyada saklanır
SEEN_FILE = "data/seen_ids.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# ── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def load_seen_ids() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set):
    os.makedirs("data", exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)


def make_id(title: str, url: str) -> str:
    """İlan başlığı + URL'den tekrarlanamaz bir ID üret."""
    raw = f"{title}|{url}"
    return hashlib.md5(raw.encode()).hexdigest()


def matches_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"[Telegram] Mesaj gönderildi: {message[:60]}...")


def send_startup_message(new_count: int, total_scanned: int):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    if new_count == 0:
        msg = (
            f"🔍 <b>ilan.gov.tr Tarama Tamamlandı</b>\n"
            f"🕐 {now}\n"
            f"📊 Taranan ilan: {total_scanned}\n"
            f"✅ Yeni Mol. Biyoloji & Genetik ilanı yok."
        )
    else:
        msg = (
            f"🔍 <b>ilan.gov.tr Tarama Tamamlandı</b>\n"
            f"🕐 {now}\n"
            f"📊 Taranan ilan: {total_scanned}\n"
            f"🆕 <b>{new_count} yeni ilan bulundu!</b> (Detaylar yukarıda)"
        )
    send_telegram(msg)


# ── Ana Tarama Mantığı ───────────────────────────────────────────────────────

def fetch_listings(page: int = 1) -> list[dict]:
    """Belirtilen sayfadaki ilanları döndür."""
    url = f"{SEARCH_URL}?page={page}"
    resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    listings = []

    # ilan.gov.tr'nin HTML yapısına göre ilan kartlarını bul
    cards = soup.select("div.ilan-list-item, article.ilan-item, div.listing-item")

    # Genel fallback: tüm başlık linkleri
    if not cards:
        cards = soup.select("a[href*='/ilan/']")
        for a in cards:
            href = a.get("href", "")
            if not href.startswith("http"):
                href = BASE_URL + href
            title = a.get_text(strip=True)
            if title and len(title) > 10:
                listings.append({"title": title, "url": href, "detail": ""})
        return listings

    for card in cards:
        title_el = card.select_one("h2, h3, .title, .ilan-baslik")
        link_el = card.select_one("a[href*='/ilan/']")
        detail_el = card.select_one(".description, .ozet, p")

        title = title_el.get_text(strip=True) if title_el else ""
        url = ""
        if link_el:
            url = link_el.get("href", "")
            if not url.startswith("http"):
                url = BASE_URL + url
        detail = detail_el.get_text(strip=True) if detail_el else ""

        if title:
            listings.append({"title": title, "url": url, "detail": detail})

    return listings


def fetch_all_listings(max_pages: int = 10) -> list[dict]:
    """Birden fazla sayfayı tara."""
    all_listings = []
    for page in range(1, max_pages + 1):
        try:
            page_listings = fetch_listings(page)
            if not page_listings:
                print(f"[Sayfa {page}] Boş, duruyorum.")
                break
            all_listings.extend(page_listings)
            print(f"[Sayfa {page}] {len(page_listings)} ilan alındı.")
            time.sleep(1.5)  # Sunucuyu yormamak için bekle
        except Exception as e:
            print(f"[Sayfa {page}] Hata: {e}")
            break
    return all_listings


def format_notification(ilan: dict) -> str:
    """Telegram bildirimi için mesaj formatı."""
    return (
        f"🎓 <b>Yeni Akademik İlan!</b>\n\n"
        f"📌 <b>{ilan['title']}</b>\n"
        f"{'📝 ' + ilan['detail'][:200] + '...' if ilan.get('detail') else ''}\n"
        f"🔗 <a href=\"{ilan['url']}\">İlana Git</a>\n\n"
        f"🏷️ #MolekulerBiyoloji #AkademikIlan #ilangovtr"
    )


# ── Ana Çalışma ──────────────────────────────────────────────────────────────

def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Tarama başlıyor...")

    seen_ids = load_seen_ids()
    all_listings = fetch_all_listings(max_pages=15)

    print(f"Toplam {len(all_listings)} ilan tarandı.")

    new_count = 0

    for ilan in all_listings:
        # Anahtar kelime eşleşmesi
        combined_text = f"{ilan['title']} {ilan.get('detail', '')}"
        if not matches_keywords(combined_text):
            continue

        ilan_id = make_id(ilan["title"], ilan["url"])

        if ilan_id in seen_ids:
            print(f"  [Zaten görüldü] {ilan['title'][:60]}")
            continue

        # Yeni ilan bulundu!
        print(f"  [YENİ İLAN] {ilan['title']}")
        try:
            send_telegram(format_notification(ilan))
            seen_ids.add(ilan_id)
            new_count += 1
            time.sleep(1)  # Telegram rate limit
        except Exception as e:
            print(f"  [Telegram Hatası] {e}")

    save_seen_ids(seen_ids)

    # Özet bildirim gönder
    send_startup_message(new_count, len(all_listings))
    print(f"Tamamlandı. {new_count} yeni ilan bildirildi.")


if __name__ == "__main__":
    main()
