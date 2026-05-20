# 🎓 ilan.gov.tr Akademik Kadro Takip Botu

**Moleküler Biyoloji ve Genetik** kadro ilanlarını her 12 saatte bir otomatik tarar,
yeni ilan bulunduğunda Telegram'a bildirim gönderir. GitHub Actions üzerinde **ücretsiz** çalışır.

---

## 📁 Dosya Yapısı

```
ilan-tracker/
├── .github/
│   └── workflows/
│       └── scrape.yml       ← GitHub Actions iş akışı
├── data/
│   └── seen_ids.json        ← Görülen ilanların kaydı (otomatik güncellenir)
├── scraper.py               ← Ana tarayıcı script
├── requirements.txt
└── README.md
```

---

## 🚀 Kurulum (Adım Adım)

### 1. Telegram Bot Oluşturun

1. Telegram'da **@BotFather**'ı açın
2. `/newbot` yazın → bot adı ve kullanıcı adı girin
3. Size verilen **Bot Token**'ı kopyalayın (`123456:ABC-DEF...`)
4. Botunuza bir mesaj gönderin
5. Tarayıcıda şu URL'yi açın (token'ınızı yazın):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
6. `"chat":{"id": XXXXXXX}` kısmındaki **Chat ID**'nizi not alın

> 💡 **Grup/Kanal için:** Botu gruba ekleyin, admin yapın, aynı adımı uygulayın.

---

### 2. GitHub Reposu Oluşturun

```bash
# Bu klasörü GitHub'a yükleyin
git init
git add .
git commit -m "İlk commit"
git remote add origin https://github.com/KULLANICI_ADI/ilan-tracker.git
git push -u origin main
```

---

### 3. GitHub Secrets Ekleyin

Repo sayfasında: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Adı | Değer |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather'dan aldığınız token |
| `TELEGRAM_CHAT_ID` | Chat ID'niz (örn: `123456789`) |
| `GH_PAT` | GitHub Personal Access Token (aşağıya bakın) |

#### GitHub Personal Access Token (GH_PAT) Oluşturma:
1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. **Generate new token** → İsim verin
3. **`repo`** iznini işaretleyin
4. Oluşturun, kopyalayın → `GH_PAT` secret'ına yapıştırın

---

### 4. İlk Çalıştırma

GitHub repo sayfasında:
**Actions → ilan.gov.tr Akademik Kadro Takip → Run workflow → Run workflow**

✅ Her şey doğruysa Telegram'a özet mesaj gelecek.

---

## ⚙️ Özelleştirme

### Farklı Alan/Bölüm Eklemek

`scraper.py` içinde `KEYWORDS` listesini düzenleyin:

```python
KEYWORDS = [
    "moleküler biyoloji",
    "genetik",
    "biyoteknoloji",       # ← ekleyin
    "biyokimya",           # ← ekleyin
]
```

### Tarama Sıklığını Değiştirmek

`.github/workflows/scrape.yml` içinde cron ifadesini düzenleyin:

```yaml
# Her 6 saatte bir
- cron: "0 */6 * * *"

# Her gün sabah 08:00 TR saati (05:00 UTC)
- cron: "0 5 * * *"
```

### Daha Fazla Sayfa Taramak

`scraper.py` içinde:
```python
all_listings = fetch_all_listings(max_pages=20)  # varsayılan: 15
```

---

## 📬 Telegram Bildirim Örneği

```
🎓 Yeni Akademik İlan!

📌 Moleküler Biyoloji ve Genetik Anabilim Dalı - Araştırma Görevlisi
📝 Adayların 15 gün içinde başvurması gerekmektedir...
🔗 İlana Git

🏷️ #MolekulerBiyoloji #AkademikIlan #ilangovtr
```

---

## ❓ Sık Sorulan Sorular

**Saat kaçta çalışır?**
Cron `0 0,12 * * *` = UTC 00:00 ve 12:00 = **TR saati 03:00 ve 15:00**

**GitHub Actions ücretsiz mi?**
Evet. Public repolar için tamamen ücretsiz, private repolar için ayda 2000 dakika ücretsiz kota var (bu bot ayda ~60 dakika kullanır).

**İlan zaten görüldüyse tekrar bildirir mi?**
Hayır. `data/seen_ids.json` dosyası görülen ilanları kaydeder, bir daha bildirim gelmez.

**Hata ayıklama?**
GitHub → Actions → Son çalışma → Logs kısmından tüm çıktıyı görebilirsiniz.
