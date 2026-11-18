# Halı dokuma salonu simülasyonu: tasarım ve iş etüdü rehberi

Bu modül, mevcut seri hat projesinin yanında, bir halı dokuma salonunda
**operatörlerin çalışma durumlarını** ve **tezgâhların dokuma durumlarını** birlikte
modeller. Amaç, iş etüdü (zaman etüdü + iş örneklemesi) ile beslenen bir model
üzerinde değişikliklerin verimliliğe etkisini önceden görmektir.

> Fabrika verisi henüz yok. Bütün parametreler `VARSAYIM` etiketlidir ve
> `data/hali/parametreler.json` dosyasında ya da paneldeki "İş etüdü" sekmesinden
> ölçümlerle değiştirilir.

## 1. Model kapsamı

| Öğe | Varsayılan | Not |
|---|---|---|
| Tezgâh | 12 adet yüz yüze jakar, 100 atkı/dk, 4 m en, 2 yüz | `tezgah_sayisi`, `devir`, `en_m`, `yuz_sayisi` |
| Ürün karması | A %50 (2.000 atkı/m), B %30 (2.500), C %20 (3.000) | Kopuş çarpanı 0,8 / 1,0 / 1,4 |
| Operatör | Ardışık 4 tezgâh / operatör (3 operatör) | `operator_basina_tezgah` |
| Teknisyen | 1 (arızalar) | `teknisyen_sayisi` |
| Çözgü ekibi | 1 (çözgü levendi değişimi, 600 m çözgü) | `cozgu_ekibi`, `cozgu_uzunlugu_m` |
| Vardiya | 3 × 8 saat, molalar 2. saatte 15, 4. saatte 30, 6. saatte 15 dk | `molalar`, `mola_duzeni` |

### Tezgâh durumları
`dokuma` · `operator_bekleme` (makine girişimi) · `atki_kopusu` · `cozgu_kopusu` ·
`top_indirme` · `ayar` (ürün/renk değişimi) · `cozgu_degisimi` · `ariza` (teknisyen bekleme + onarım)

### Operatör durumları
`atki_kopusu` · `cozgu_kopusu` · `top_indirme` · `ayar` · `besleme` (iplik/bobin; tezgâhı
durdurmaz) · `yurume` · `gozetim` (boş/gözetim) · `mola` · `kisisel`

İş etüdü sınıflaması: verimli iş (müdahaleler, top, ayar, besleme), yardımcı iş (yürüme),
boş/gözetim, mola ve kişisel.

### Mantık
- Dokuma sırasında atkı kopuşu, çözgü kopuşu, arıza ve besleme ihtiyacı yarışır
  (sıklıklar *dokuma saati* başınadır). Top bitince top indirme; sonraki sipariş başka
  kaliteyse ayar. Çözgü bitince çözgü ekibi çağrılır.
- Operatör, sorumlu olduğu tezgâhlardaki işleri seçim kuralına göre alır:
  `fifo`, `en_yakin` veya `oncelikli` (tezgâhı durduran iş besleme işinden önce).
  Tezgâha yürür (tezgâh aralığı × 0,15 dk + 0,1 dk), işi yapar.
- Mola ve kişisel ihtiyaç iş aralarında kullanılır. Mola düzenleri:
  `toplu` (herkes aynı anda, tezgâhlara kimse bakmaz), `kademeli` (komşu iki operatör
  sırayla çıkar ve birbirine bakar), `yedek` (operatörler sırayla çıkar, yüzer yedek
  operatör bakar).
- Ortak rastgele sayılar: her tezgâh/operatör ve amaç için ayrı rastgele sayı akışı;
  senaryolar aynı tohumlarla koşar, farklar eşleştirilmiş t aralığıyla verilir.

## 2. Senaryolar

| Kod | Değişiklik |
|---|---|
| H0 | Temel |
| H1 / H2 | Operatör başına 3 / 6 tezgâh |
| H3 / H4 | Kademeli mola / yedek operatörle sırayla mola |
| H5 | İplik kalitesi: kopuşlar %30 az |
| H6 | SMED: ayar ve çözgü değişimi %40 kısa |
| H7 | Önleyici bakım: arıza aralığı ×1,5 |
| H8 | Öncelik kuralı: duran tezgâh önce |
| H9 | Yerleşim: yürüme %50 kısa |
| H10 | Tezgâh hızı +%10, kopuş +%20 |

Yeni senaryo eklemek için `src/hali/senaryo.py` içindeki `SENARYOLAR` sözlüğüne bir satır
eklemek yeterlidir.

## 3. İş etüdünde toplanacak veri

Form şablonları `data/hali/is_etudu/` altındadır (örnek satırlar `ORNEK` etiketlidir, silin).

| Form | Ne ölçülür | Modelde nereye gider | Önerilen miktar |
|---|---|---|---|
| `zaman_etudu.csv` | Atkı/çözgü kopuşu düzeltme, top indirme, ayar, besleme, çözgü değişimi süreleri + performans puanı | `atki_mudahale`, `cozgu_mudahale`, `top_indirme`, `ayar`, `besleme_sure`, `cozgu_degisim` (normal süre dağılımı) | Eleman başına en az 30 döngü; `gerekli_n` sütunu yeterliliği söyler |
| `is_ornekleme.csv` | Rastgele zamanlı turlarda her operatör ve tezgâhın durumu | Model doğrulaması: model oranları sahadaki güven aralığında mı? | ≥100 tur (12 tezgâh, 3 operatörle ±3-4 puan); bkz. sanal örnekleme |
| `kopus_kayitlari.csv` | Kopuş anı, operatörün gelişi, bitiş; tür, ürün | `atki_kopus_saat`, `cozgu_kopus_saat`, müdahale dağılımı; bekleme süresi doğrulama için | Birkaç vardiya, tüm tezgâhlar |
| `ariza_kayitlari.csv` | Arıza başlangıcı, teknisyen gelişi, onarım bitişi | `ariza_mtbf_saat`, `ariza_onarim` | Mümkün olan en uzun dönem (bakım kayıtları) |

Ayrıca bilinmesi gerekenler: tezgâh sayısı ve yerleşimi, tezgâh hızı, ürün karması ve atkı
sıklıkları, top uzunlukları, çözgü uzunluğu, operatör-tezgâh ataması, vardiya/mola düzeni.

**Önemli:** Modele *normal süre* (gözlenen süre × performans puanı) girer. Mola ve kişisel
ihtiyaç modelde ayrı olaylardır; standart süredeki tolerans payını eklemek kayıpları iki kez sayar.

### İş akışı
1. Sanal iş örneklemesi ile gözlem planı yapın (`results/hali/is_ornekleme_yakinsama.csv`,
   panelde "İş etüdü" sekmesi).
2. Formları doldurun; `ie.zaman_etudu_analiz`, `ie.kopus_analiz`, `ie.ariza_analiz` ile
   analiz edin; `ie.parametreleri_guncelle` ile parametreleri yazın, JSON olarak kaydedin.
3. Sahadaki iş örneklemesini `ie.karsilastir(saha, ie.gercek_oranlar(model_sonucu))` ile modelle
   karşılaştırın (doğrulama). Uyuşmayan durumlar için parametreleri gözden geçirin.
4. Doğrulanmış modelle senaryoları koşun.

```python
import pandas as pd
from src.hali import is_etudu as ie
from src.hali.parametre import HaliParam

p = HaliParam()
zt = ie.zaman_etudu_analiz(pd.read_csv("data/hali/is_etudu/zaman_etudu.csv"))
kt = ie.kopus_analiz(pd.read_csv("data/hali/is_etudu/kopus_kayitlari.csv"), dokuma_saati=850)
p = ie.parametreleri_guncelle(p, zaman=zt, kopus=kt)
p.kaydet("data/hali/parametreler_olcum.json")
```
