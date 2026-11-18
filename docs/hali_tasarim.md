# Halı dokuma salonu simülasyonu: tasarım

Bu modül, fabrikanın 14 yüz yüze halı tezgâhını, her tezgâhtaki operatör ve telciyi, renk
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
| Atkı kopuşu, top indirme, desen ayarı, halı kontrolü/düzeltme | Operatör | Kontrol hariç evet |
| Çözgü/hav kopuşu, bobin/cağlık besleme | Telci | Besleme hariç evet |
| Renk değişimi | Ekip (%85), kalan operatör | Evet |
| Çözgü değişimi | Çözgü ekibi | Evet |
| Arıza | Teknisyen (2) | Evet |

Rol eşlemesi `is_rolleri` parametresindedir. Mola düzenleri: `toplu`, `kademeli` (aynı roldeki
komşu bakar), `capraz` (aynı tezgâhın operatörü ve telcisi birbirine bakar), `yedek`
(personel dalgalar halinde çıkar, yüzer yedekler bakar).

## Senaryolar

H0 temel · H1 kademeli mola · H2 çapraz mola · H3 yedekli mola · H4 1 telci/2 tezgâh ·
H5 1 operatör/2 tezgâh · H6 H4 + çapraz mola · H7 2 renk ekibi · H8 renk değişimi SMED −%40 ·
H9 kopuş −%30 · H10 MTBF ×1,5 · H11 devir +%10 (kopuş +%20). Yeni senaryo için
`src/hali/senaryo.py` içindeki `SENARYOLAR` sözlüğüne bir satır eklenir.

## Formlar (`data/hali/is_etudu/`)

| Form | Modelde |
|---|---|
| `zaman_etudu.csv` | İş sürelerinin dağılımı (normal süre) |
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
