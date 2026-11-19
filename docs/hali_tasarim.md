# Halı dokuma salonu simülasyonu: tasarım

Bu modül, fabrikanın 14 yüz yüze halı tezgâhını, her tezgâhtaki halfeyi (dokuma ustası) ve telciyi (yardımcısı), renk
değişimi ekibini, teknisyenleri ve çözgü ekibini birlikte modeller. Amaç, iş etüdü ile
beslenen bir model üzerinde değişikliklerin **m²/vardiya**ya ve çalışma/dokuma durumlarına
etkisini önceden görmektir. Ölçüm ve kullanım adımları için ayrıntılı rehber: "Halı Dokuma
İş Etüdü Rehberi" (Claude Docs).

## Kaynak etiketleri

- `FABRİKA`: fabrikadan gelen sabit bilgi (tezgâh listesi, personel düzeni, renk ekibinin varlığı)
- `VARSAYIM`: henüz ölçülmedi (devir dağılımı, sıra sıklığı, kopuş, süreler, olasılıklar)
- `ÖLÇÜM: ...`: iş etüdünden geldi (`python -m src.hali.is_etudu analiz` yazar)

## Tezgâhlar

| Tezgâh | Marka | Tarak (10 cm) | En | Renk | Tarak sayısı |
|---|---|---|---|---|---|
| T01 | Schönherr | 42 | 5 m | 8 | 2100 |
| T02, T05, T13, T14 | Van De Wiele | 42 | 4 m | 7 | 1680 |
| T03, T04 | Van De Wiele | 42 | 4 m | 7 | 1716 |
| T06 | Schönherr | 50 | 4 m | 6 | 2000 |
| T07, T08 | Schönherr | 50 | 4 m | 8 | 2000 |
| T09 | Van De Wiele-Schönherr | 50 | 4 m | 8 | 2000 |
| T10 | Van De Wiele | 50 | 4 m | 8 | 2020 |
| T11 | Schönherr | 70 | 4 m | 8 | 2800 |
| T12 | Van De Wiele | 50 | 4 m | 8 | 2000 |

Üretim hızı: m/dk = devir ÷ (sıra/m × sıra başına atkı); m² = boy × en × 2 yüz.
Varsayımlar: devir Üçgen(70, 85, 100) /dk, her yeni topta yeniden çekilir; sıra sıklığı
tarak × 1,5 (10 cm'de); 2 atkılı sistem; 8 renkli ve sık tezgâhlarda kopuş biraz daha sık.

## Personel ve işler

| İş | Rol (varsayım) | Tezgâhı durdurur mu |
|---|---|---|
| Atkı kopuşu, top indirme, desen ayarı, halı kontrolü/düzeltme | Halfe | Kontrol hariç evet |
| Çözgü/hav kopuşu, bobin/cağlık besleme | Telci | Besleme hariç evet |
| Renk değişimi | Ekip (%85), kalan halfe | Evet |
| Çözgü değişimi | Çözgü ekibi | Evet |
| Arıza | Teknisyen (2) | Evet |

Rol eşlemesi `is_rolleri` parametresindedir. `telci_yardim=True` iken telci, kendi
tezgâhındaki `yardim_isleri`ni (varsayılan atkı kopuşu ve kontrol) halfe meşgulse üstlenir.

## Mola

İki ayrı seçim:

| Parametre | Seçenekler |
|---|---|
| `mola_zamani` | `toplu`: herkes aynı anda çıkar · `ayri`: personel `mola_dalga_sayisi` dalga halinde ayrı ayrı çıkar |
| `mola_kapsama` | `yok`: kimse bakmaz · `komsu`: aynı roldeki komşu bakar · `capraz`: aynı tezgâhın halfesi ve telcisi birbirine bakar · `yedek`: `yedek_sayisi` kadar yüzer personel bakar |

Herkes aynı anda çıkarsa komşu ya da çapraz kapsama işe yaramaz (bakacak kişi de moladadır);
yalnızca yedek personel bakabilir.

## Yorgunluk ve öğrenme

- **Yorgunluk:** iş süresi × (1 + min(`yorgunluk_orani` × son moladan/vardiya başından beri saat,
  `yorgunluk_tavan`)); gece vardiyasına `yorgunluk_gece_ek` eklenir. Molada sıfırlanır.
  Varsayılan saatte %3, tavan %25 (VARSAYIM).
- **Öğrenme:** `deneyim` listesindeki kişiler (ad, başlangıç tekrar sayısı) için iş süresi ×
  max(1, (tekrar / `ogrenme_standart_tekrar`)^log2(`ogrenme_orani`)); tekrar iş türü başına sayılır.
  Varsayılan oran 0,85, standart süreye 500. tekrarda ulaşılır (VARSAYIM). Listede olmayan deneyimlidir.
- **Ölçüm:** zaman etüdü formuna `mola_sonrasi_dk` (gözlem anında son moladan beri geçen dakika) ve yeni
  personel için `tekrar` (o işi kaçıncı kez yaptığı) yazılır. `yorgunluk_analiz` saat başına artışı
  doğrusal regresyonla, `ogrenme_analiz` Wright eğrisini log-log regresyonla tahmin eder; analiz
  komutu bunları parametrelere `ÖLÇÜM` olarak yazar. Yorgunluk etkisi küçük ve eleman süreleri
  değişken olduğundan anlamlı bir eğim için yüzlerce gözlem gerekir.

## Senaryolar

H0 temel (herkes aynı anda mola) · H1 ayrı mola + komşu · H2 ayrı mola + halfe↔telci · H3 ayrı mola +
yedek · H4 1 telci/2 tezgâh · H5 1 halfe/2 tezgâh · H6 H4 + H2 · H7 2 renk ekibi · H8 renk değişimi
SMED −%40 · H9 kopuş −%30 · H10 MTBF ×1,5 · H11 devir +%10 (kopuş +%20) · H12 telci yardımı ·
H13 yorgunluk yok · H14 yorgunluk ×2 · H15 4 yeni halfe (öğrenme). Yeni senaryo için
`src/hali/senaryo.py` içindeki `SENARYOLAR` sözlüğüne bir satır eklenir.

## Formlar (`data/hali/is_etudu/`)

| Form | Modelde |
|---|---|
| `zaman_etudu.csv` | İş sürelerinin dağılımı (normal süre); `mola_sonrasi_dk` ve `tekrar` sütunlarıyla yorgunluk ve öğrenme |
| `is_ornekleme.csv` | Doğrulama: durum oranları (tur bazında güven aralığı) |
| `kopus_kayitlari.csv` | Kopuş sıklığı, müdahale süresi, bekleme |
| `ariza_kayitlari.csv` | MTBF, onarım süresi |
| `renk_degisimi_kayitlari.csv` | Renk değişimi süresi, ekip payı |
| `devir_kayitlari.csv` | Tezgâh başına devir dağılımı |
| `uretim_kayitlari.csv` | Doğrulama: m²/vardiya |

Örnek satırlar `ORNEK` etiketlidir ve analizde atlanır. `python -m src.hali.is_etudu ornek`
modelden sentetik bir saha veri seti üretir (`data/hali/ornek_saha/`), böylece analiz
zinciri gerçek veri gelmeden denenebilir.

Modele *normal süre* girer: mola ve kişisel ihtiyaç modelde ayrı olaylardır, standart süredeki
tolerans payı eklenirse kayıplar iki kez sayılır.
