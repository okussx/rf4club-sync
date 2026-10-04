# RF4Club Sync

RF4Club Sync, Russian Fishing 4 yakalama ekranını salt okunur biçimde
izler ve yakalamaları oyuncunun RF4Club profiline gönderir.
Oyuncu Bilgileri > İstatistikler ekranı açıldığında oyun istatistiklerini de
okuyup aynı profile aktarır.

[Windows ZIP paketini indir (v1.1.1)](https://github.com/okussx/rf4club-sync/releases/download/v1.1.1/RF4Club-Sync-Windows-v1.1.1.zip)

## Güvenlik sınırı

Logger oyuna hiçbir klavye veya fare girdisi göndermez. Tıklama, tuş basma,
pencere değiştirme veya oyun otomasyonu yapmaz. Yalnızca ekran görüntüsü alır,
belirlenen bölgelerde OCR çalıştırır ve sonucu RF4Club API'sine gönderir.

## Kayıt bütünlüğü

RF4Club Sync yalnız RF4 penceresi ön planda ve ekranı kaplayacak durumda olduğunda
yakalama kabul eder. KEEP/TUT ekranının kaybolup yeniden görünmesini bekleyerek tek
ekrandan tekrar tekrar kayıt üretmez. Sunucu görüntü parmak izi tekrarlarını ve
gerçekçi olmayan hızdaki gönderimleri reddeder.

Bu kontroller manipülasyonu zorlaştırır ancak RF4 tarafından sağlanan resmi bir
telemetri veya kriptografik oyun imzası olmadığı için istemci ekran verisi tek
başına mutlak doğrulama sayılamaz. Oyuncu kayıtları ayrı kaynak sınıfında tutulur;
doğrulama sürecinden geçmeden canonical analitik veriye dönüştürülmez. Trophy ve
Super Trophy kayıtlarının tam ekran görüntüsü denetim için saklanır.

## Davranış

- RF4 işlemi çalışmıyorsa bekler.
- Yakalama ekranındaki `KEEP` / `TUT` yazısını tetik olarak kullanır.
- Balık adını ve varsa turuncu `Trophy / Ödül / Ganimet` ya da mavi
  `Rare Trophy / Süper Ödül / Süper Ganimet` etiketini okur.
- Her yakalama için RF4Club profilinde tek kayıt oluşturur.
- Normal yakalamalarda tam ekran görüntüsü kaydetmez veya göndermez.
- Yalnız Trophy ve Super Trophy yakalamalarında tam ekran görüntüsünü kaydeder
  ve profile gönderir.
- Bağlantı yoksa kaydı yerel kuyruğa alır ve daha sonra tekrar gönderir.
- Aynı olay tekrar gönderilse bile sunucu tarafındaki idempotency anahtarı ikinci
  bir kart oluşturulmasını engeller.
- Sunucu yakalamayı başarıyla kabul ettiğinde kısa bir Windows bildirim sesi
  çalar. `RF4CLUB_SYNC_SOUND=0` ayarıyla kapatılabilir.
- İstatistik ekranını en fazla beş dakikada bir okur; aynı açık ekranı sürekli
  yeniden göndermez.

## Kullanıcı kurulumu

ZIP paketini çıkardıktan sonra `RF4Club-Sync-Setup-v1.1.1.exe` dosyasını çalıştır. Kurulum uygulamayı kullanıcı
hesabına kurar ve masaüstü ile Başlat menüsüne **RF4Club Sync** kısayolu ekler.
Python, pip, PyTorch veya OCR modeli ayrıca kurulmaz; bunlar uygulama paketinin
içindedir.

RF4Club sitesinde oturum aç, profilindeki **Eşleştirme Kodu Oluştur** düğmesine
bas, kısayoldan RF4Club Sync'i başlat ve sekiz karakterli kodu bir kez gir.
Sonraki çalıştırmalarda kod yeniden istenmez. Uygulama doğrudan
`https://rf4club.com` adresine bağlanır.

## Kaynak koddan geliştirme kurulumu

ZIP dosyasını bir klasöre çıkardıktan sonra `SETUP.bat` dosyasına çift tıkla.
Kurulum Python ortamını oluşturur ve gerekli OCR paketlerini indirir. Bu işlem
ilk seferde birkaç dakika sürebilir. EasyOCR, metin tanıma için PyTorch ve
görüntü işleme bağımlılıklarını kullandığından ilk kurulum yüzlerce MB olabilir.

Kurulum tamamlandıktan sonra `START.bat` dosyasına çift tıkla ve sitedeki
sekiz karakterli eşleştirme kodunu gir.

Sonraki çalıştırmalarda yalnız `START.bat` dosyasına çift tıklamak yeterlidir.

Varsayılan API adresi `https://rf4club.com` değeridir. Geliştirme sunucusu için:

```powershell
$env:RF4CLUB_API_URL = "http://localhost:3000"
python rf4club_sync.py
```

Dağıtılabilir Windows kurulum paketini üretmek için `build-windows.ps1`
çalıştırılır. Çıktı `release/RF4Club-Sync-Setup-v1.1.1.exe` olur.

## OCR bölgeleri

`config.py` içindeki koordinatlar 1920x1080 referans çözünürlüğüne göredir ve
ekran çözünürlüğüne otomatik ölçeklenir:

- `KEEP_REGION`: KEEP/TUT butonunun bulunduğu alan.
- `FISH_HEADER_REGION`: balık adı ile Trophy/Super Trophy yazısının bulunduğu alan.
- `STATISTICS_TRIGGER_REGION`: Oyuncu Bilgileri/İstatistikler ekranını doğrular.
- `STATISTICS_SUMMARY_REGION` ve kart bölgeleri: profil özet değerlerini okur.
- `STATISTICS_RECORDS_REGION`: kişisel rekor kartlarının metnini okur.

Referans ekran 1920x1080 ve oyun arayüz ölçeği 0,75'tir. Bölgeler diğer ekran
çözünürlüklerine otomatik ölçeklenir.

## Yerel dosyalar

Yerel veriler `%LOCALAPPDATA%\RF4Club Sync` klasöründedir:

- `rf4_catches.csv`: yakalamaların küçük yerel denetim kaydı.
- `rf4_raw_ocr_log.csv`: OCR hata ayıklama verisi.
- `trophy_screenshots/`: yalnız Trophy/Super Trophy tam ekran görüntüleri.
- `pending_sync/`: bağlantı kurulana kadar bekleyen gönderimler.
- `device.json`: gizli cihaz anahtarı; paylaşılmamalıdır.
- `statistics-state.json`: beş dakikalık istatistik bekleme durumu.

Logger'ı durdurmak için terminalde `Ctrl+C` kullanılır.

## Lisans ve atıf

RF4Club Sync değişiklikleri Copyright 2026 RF4Club contributors. Proje, Apache
License 2.0 kapsamında dağıtılan Russian-fishing-4-data-syphon çalışmasından
türetilmiştir. Orijinal lisans ve atıf korunur; ayrıntılar `LICENSE` ve `NOTICE`
dosyalarındadır.
