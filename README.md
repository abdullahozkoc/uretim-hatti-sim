# SimPy Üretim Hattı Simülasyonu

Python ve SimPy ile beş istasyonlu seri bir üretim hattının ayrık olay simülasyonu. Proje, "hatta bir operatör ya da tampon eklersem çıktı ne kadar artar?" sorusuna, çoklu replikasyon ve %95 güven aralığıyla cevap veriyor.

![Panel](docs/panel.png)

## Hızlı başlangıç

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pytest                           # 28 test, ~45 sn
python -m src.mm1_dogrulama      # M/M/1 doğrulama tablosu  -> results/mm1_dogrulama.md
python -m src.deney              # senaryolar, Welch, tampon eğrisi -> results/deney_raporu.md
streamlit run app/panel.py       # parametre paneli
```

## Sonuçlar

### M/M/1 doğrulaması (μ = 1)

| ρ | Rep. | Teorik W_q | Sim. W_q (±%95 GA) | Sapma | Teorik L_q | Sim. L_q (±%95 GA) | Sapma |
|---|---|---|---|---|---|---|---|
| 0,5 | 30 | 1,0 | 0,999 ± 0,009 | −%0,07 | 0,5 | 0,500 ± 0,005 | −%0,08 |
| 0,8 | 30 | 4,0 | 4,007 ± 0,038 | +%0,17 | 3,2 | 3,207 ± 0,032 | +%0,23 |
| 0,9 | 50 | 9,0 | 9,017 ± 0,064 | +%0,18 | 8,1 | 8,115 ± 0,059 | +%0,19 |

Hedef %2-3 idi; en büyük sapma %0,23. Little yasası farkı en fazla %0,06.

### What-if senaryoları (30 replikasyon, ortak rastgele sayılar)

5.000 dk ölçüm ve 500 dk ısınma. Δ sütunları S0'a göre eşleştirilmiş farktır; köşeli parantez %95 güven aralığıdır.

| Senaryo | Verim (ürün/saat) | Çevrim süresi (dk) | Ortalama WIP | Darboğaz | Δ verim |
|---|---|---|---|---|---|
| S0 Temel durum | 18,64 ± 0,25 | 43,1 ± 0,6 | 13,43 ± 0,17 | İstasyon 3 | – |
| S1 Darboğaza ikinci operatör | 23,98 ± 0,27 | 30,5 ± 0,7 | 12,20 ± 0,32 | İstasyon 2 | +5,34 [+5,09, +5,58] |
| S2 Tampon büyütme (5→10) | 19,21 ± 0,23 | 70,8 ± 1,1 | 22,72 ± 0,31 | İstasyon 3 | +0,56 [+0,51, +0,62] |
| S3 Hat dengeleme | 21,25 ± 0,33 | 34,7 ± 1,0 | 12,30 ± 0,36 | İstasyon 3 | +2,60 [+2,50, +2,71] |
| S4 Arıza azaltma (MTBF 180→300) | 19,62 ± 0,26 | 41,1 ± 0,6 | 13,45 ± 0,18 | İstasyon 3 | +0,98 [+0,79, +1,17] |

**Yorum**

- **S1 en büyük kazancı veriyor** (+%29 verim) ve aynı anda çevrim süresini ve WIP'i düşürüyor. Darboğaz İstasyon 3'ten **İstasyon 2'ye** kayıyor; dokümanda tahmin edilen İstasyon 4 değil. Sebep: arızalarla birlikte İstasyon 2'nin etkin süresi (≈2,35 dk) İstasyon 4'ünkünden (≈2,16 dk) daha uzun.
- **S2 verimi yalnızca +%3 artırıyor** ama WIP'i 13,4'ten 22,7'ye, çevrim süresini 43'ten 71 dakikaya çıkarıyor. Dokümandaki "tampon büyütmek WIP'i şişirebilir" uyarısı sayılarla doğrulanıyor.
- **S3** darboğazı çözmeden verimi +%14 artırıyor; İstasyon 3 hâlâ en yüksek kullanımda ama fark daralıyor.
- **S4** verimi +%5 artırıyor, WIP değişmiyor (fark anlamsız).
- Tüm verim farkları istatistiksel olarak anlamlı (aralıklar sıfırı içermiyor).

Tam rapor, kullanım tablosu ve grafikler: [results/deney_raporu.md](results/deney_raporu.md).

### Isınma süresi (Welch)

30 replikasyonluk ısınmasız koşularda hattaki WIP yaklaşık 130 dakikada, saatlik çıkış yaklaşık 120 dakikada kararlı duruma oturuyor. Kullanılan 500 dk ısınma bunun yaklaşık 4 katı, yani dokümandaki karar güvenli tarafta.

## Model varsayımları

- **Hat:** 5 istasyon, istasyonlar arasında `simpy.Store(capacity=k)` ara stoklar. İlk istasyonun önünde sınırsız hammadde var.
- **Bloklanma:** İşini bitiren istasyon, sonraki ara stok doluysa parçayı elinde tutarak bekler (blocking after service).
- **İstasyon kapasitesi:** `kapasite` kadar paralel sunucu. Her sunucunun kendi arıza süreci var.
- **Arızalar:** Arızalar takvim zamanına göre gelir; arızalar arası süre üstel dağılımlı (ortalaması MTBF), onarım süresi de üstel dağılımlı (ortalaması MTTR). İşlem sırasında gelen arızada kalan süre onarımdan sonra tamamlanır. Makine boşta ya da bloklu iken de arızalanabilir.
- **İşlem süreleri:** Normal dağılımlı süreler 0,1 dk ile alttan kesilir. İstasyon 3'ün üçgen dağılımının (2,0 / 2,6 / 3,4) gerçek ortalaması 2,67 dk'dır, 2,6 değil.
- **Rastgele sayılar:** Replikasyon tohumundan `SeedSequence` ile her sunucuya ayrı işlem ve arıza akışları türetiliyor. Böylece aynı tohum aynı sonucu verir ve senaryolar arasında ortak rastgele sayılar iyi eşleşir.
- **Darboğaz kuralı:** Kullanımı (çalışma + arıza) en yüksek istasyon darboğaz sayılır. Eşitlik durumunda önünde en uzun kuyruk biriken istasyon seçilir.

## Doğrulama durumu

| Kontrol | Durum |
|---|---|
| M/M/1 teorik karşılaştırma | ✅ en büyük sapma %0,23 |
| Little yasası (hat) | ✅ fark %0,5 altında |
| Uç durumlar (sabit süre, arıza yok, sonsuz tampon) | ✅ el hesabıyla birebir |
| Tekrarlanabilirlik | ✅ aynı tohum, özdeş çıktı |
| Korunum (giren = çıkan + sistemde) | ✅ |
| Olay günlüğü (sıra, FIFO) | ✅ otomatik testte |
| Darboğaz tespiti | ✅ S0'da 10/10 replikasyonda İstasyon 3 |
| Gerçek veriyle karşılaştırma (validation) | ⏳ **bekliyor**: gerçek hat verisi yok. Model gerçek sisteme uyum iddiasında bulunmaz. |
| Uzman değerlendirmesi | ⏳ bekliyor |

## Yol haritası

- [x] Hafta 1: M/M/1 doğrulandı
- [x] Hafta 2: Hat modeli ve metrikler çalışıyor
- [x] Hafta 3: Senaryo karşılaştırma tablosu dolu
- [x] Hafta 4: Panel ve README tamam (panel güncellemesi ~2 sn)
- [ ] Depo yayında (GitHub deposu bekleniyor)

### Yeni hedefler (doküman sonrası)

Tamamlananlar:

- [x] **Gereken replikasyon sayısını otomatik bulma:** Hedef bağıl yarı genişliğe göre replikasyon ekleniyor (`deney.gerekli_replikasyon`). S0 verimi için %1 hassasiyet 55 replikasyon gerektiriyor.
- [x] **Tampon duyarlılık eğrisi:** k = 1…20 için verim, WIP ve çevrim süresi (`results/tampon_duyarlilik.png`). Azalan getiri görülüyor: k = 5'ten 20'ye çıkmak verimi yalnızca %5 artırıyor, WIP'i ise 3 katına çıkarıyor.
- [x] **Kalibrasyon araçları:** `src/kalibrasyon.py` dosyası dağılım uydurma ve KS testi yapıyor, arıza kayıtlarından MTBF ve MTTR hesaplıyor, ölçülen sürelerden `IstasyonParam` üretiyor. Staj verisi geldiğinde doğrudan kullanılabilir.
- [x] **Otomatik test (CI):** `.github/workflows/test.yml` dosyası her push'ta testleri Python 3.11-3.13 ile koşuyor.

Öneriler (henüz yapılmadı, kapsamı değiştirdiği için onay bekliyor):

1. **Gerçek veriyle validation:** Staj hattından 100-200 süre ölçümü ve duruş kayıtları alınıp model verimi gerçek verimle karşılaştırılır (hedef: %5-10 fark).
2. **Ekonomik değerlendirme:** Senaryolara yatırım ve işletme maliyeti eklenir (ör. ikinci operatörün saatlik maliyeti ve ara stok alanı). Böylece karşılaştırmaya "verim artışı başına maliyet" ve geri ödeme süresi eklenir.
3. **Tampon dağıtımı optimizasyonu:** Toplam tampon sayısı sabitken en iyi dağılım aranır (simülasyon tabanlı optimizasyon). İlk sürümde kapsam dışıydı.
4. **Ürün çeşitliliği ve hazırlık süreleri:** Halı dokuma planlama projesiyle bağlantı kurulur.
5. **OEE projesiyle entegrasyon:** Modelden OEE (kullanılabilirlik × performans × kalite) hesaplanır ve gerçek OEE verisiyle karşılaştırılır.

## Klasör yapısı

```text
src/
  mm1.py            # Model 1: tek istasyon (doğrulama referansı)
  mm1_dogrulama.py  # M/M/1 doğrulama tablosu
  hat.py            # Model 2: seri üretim hattı
  istatistik.py     # durum ve seviye kaydediciler
  deney.py          # replikasyon, senaryolar, Welch, duyarlılık
  analiz.py         # güven aralığı, eşleştirilmiş fark, hareketli ortalama
  kalibrasyon.py    # dağılım uydurma, MTBF/MTTR
app/panel.py        # Streamlit arayüzü
tests/              # test_mm1, test_hat, test_deney, test_panel
results/            # üretilen tablolar ve grafikler
data/               # gerçek veri (git'e eklenmez)
```

## Proje özeti (CV ve mülakat için)

> Python/SimPy ile 5 istasyonlu, arızalı ve sınırlı ara stoklu bir seri üretim hattının ayrık olay simülasyonunu kurdum. Modeli önce M/M/1 kuyruk teorisiyle doğruladım (sapma %0,3'ün altında), ardından Welch yöntemiyle ısınma süresini belirledim. Dört iyileştirme senaryosunu ortak rastgele sayılar ve eşleştirilmiş t güven aralıklarıyla karşılaştırdım. Darboğaza ikinci operatör eklemek verimi %29 artırdı ve darboğazı bir önceki istasyona taşıdı. Tamponu büyütmek ise verimi yalnızca %3 artırırken çevrim süresini %64 uzattı. Sonuçlar, parametreleri 2 saniyede güncelleyen bir Streamlit panelinde sunuluyor; projede 28 otomatik test var.
