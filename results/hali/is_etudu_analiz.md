# İş etüdü analizi

## Zaman etüdü (deneyimli personel)

| eleman                    | model_alani    |   n |   gozlenen_ort |   gozlenen_ss |   performans_ort |   normal_sure |   tolerans |   standart_sure |   gerekli_n | yeterli   | dagilim                         |
|:--------------------------|:---------------|----:|---------------:|--------------:|-----------------:|--------------:|-----------:|----------------:|------------:|:----------|:--------------------------------|
| Atkı kopuşu düzeltme      | atki_mudahale  |  60 |          1.219 |         0.335 |          100.417 |         1.218 |       0.15 |           1.401 |         117 | False     | Normal(1.21783, ss 0.319657)    |
| Çözgü/hav kopuşu düzeltme | cozgu_mudahale |  60 |          2.773 |         0.692 |          100.083 |         2.77  |       0.15 |           3.186 |          96 | False     | Normal(2.77005, ss 0.690834)    |
| Top indirme               | top_indirme    |  60 |         10.518 |         1.977 |          100.417 |        10.527 |       0.15 |          12.106 |          55 | True      | Lognormal(10.527, ss 1.94324)   |
| Desen ayarı               | ayar           |  54 |         24.743 |         7.076 |          101.389 |        24.902 |       0.15 |          28.637 |         126 | False     | Üçgen(10.6931, 21.208, 41.784)  |
| Bobin/cağlık besleme      | besleme_sure   |  60 |          3.341 |         0.635 |          100.667 |         3.347 |       0.15 |           3.849 |          56 | True      | Lognormal(3.34684, ss 0.585729) |
| Halı kontrolü             | kontrol_sure   |  60 |          4.428 |         1.258 |           98.917 |         4.372 |       0.15 |           5.028 |         125 | False     | Üçgen(1.97749, 3.393, 7.99111)  |

## Yorgunluk

Süre, moladan sonraki her saat için %0.7 uzuyor (%95 YG %-3.9 … %5.4, n=354, anlamsız: parametre değiştirilmedi).

## Öğrenme eğrisi

Öğrenme oranı 0.89 (tekrar iki katına çıkınca süre ×0.89); standart süreye yaklaşık 998. tekrarda ulaşılıyor (n=281).

## İş örneklemesi (saha)

| kaynak_tipi   | durum            |   gozlem |   toplam |   oran |   tur_sayisi |   gerekli_tur |   alt |   ust |   gerekli_n |
|:--------------|:-----------------|---------:|---------:|-------:|-------------:|--------------:|------:|------:|------------:|
| halfe         | atki_kopusu      |       14 |      630 |  0.022 |           45 |             7 | 0.01  | 0.034 |          93 |
| halfe         | top_indirme      |       13 |      630 |  0.021 |           45 |             5 | 0.011 | 0.03  |          87 |
| halfe         | ayar             |       14 |      630 |  0.022 |           45 |             6 | 0.011 | 0.033 |          93 |
| halfe         | renk_degisimi    |        6 |      630 |  0.01  |           45 |             3 | 0.002 | 0.017 |          41 |
| halfe         | kontrol          |       68 |      630 |  0.108 |           45 |            48 | 0.076 | 0.14  |         411 |
| halfe         | gozetim          |      375 |      630 |  0.595 |           45 |           388 | 0.505 | 0.686 |        1029 |
| halfe         | mola             |      111 |      630 |  0.176 |           45 |           578 | 0.066 | 0.287 |         620 |
| halfe         | kisisel          |       29 |      630 |  0.046 |           45 |            14 | 0.029 | 0.063 |         188 |
| telci         | cozgu_kopusu     |       40 |      630 |  0.063 |           45 |            18 | 0.045 | 0.082 |         254 |
| telci         | besleme          |       35 |      630 |  0.056 |           45 |            22 | 0.034 | 0.077 |         224 |
| telci         | gozetim          |      422 |      630 |  0.67  |           45 |           465 | 0.571 | 0.769 |         944 |
| telci         | mola             |      109 |      630 |  0.173 |           45 |           599 | 0.061 | 0.286 |         611 |
| telci         | kisisel          |       24 |      630 |  0.038 |           45 |            13 | 0.022 | 0.054 |         157 |
| tezgah        | dokuma           |      432 |      630 |  0.686 |           45 |           195 | 0.622 | 0.75  |         920 |
| tezgah        | personel_bekleme |       70 |      630 |  0.111 |           45 |           211 | 0.044 | 0.178 |         422 |
| tezgah        | atki_kopusu      |       14 |      630 |  0.022 |           45 |             7 | 0.01  | 0.034 |          93 |
| tezgah        | cozgu_kopusu     |       40 |      630 |  0.063 |           45 |            18 | 0.045 | 0.082 |         254 |
| tezgah        | top_indirme      |       13 |      630 |  0.021 |           45 |             5 | 0.011 | 0.03  |          87 |
| tezgah        | ayar             |       14 |      630 |  0.022 |           45 |             6 | 0.011 | 0.033 |          93 |
| tezgah        | renk_degisimi    |       27 |      630 |  0.043 |           45 |            18 | 0.024 | 0.062 |         176 |
| tezgah        | cozgu_degisimi   |        8 |      630 |  0.013 |           45 |             4 | 0.004 | 0.021 |          54 |
| tezgah        | ariza            |       12 |      630 |  0.019 |           45 |             7 | 0.007 | 0.031 |          80 |

Dokuma saati = 14 tezgâh × 120 saat × 0.69 = 1152 saat

## Kopuşlar

| tur   |   adet |   saat_basina |   ort_bekleme_dk |   ort_mudahale_dk | mudahale_dagilim                |
|:------|-------:|--------------:|-----------------:|------------------:|:--------------------------------|
| atki  |   1760 |         1.528 |            1.861 |             1.244 | Lognormal(1.24395, ss 0.396898) |
| cozgu |   2421 |         2.102 |            1.717 |             2.925 | Üçgen(1.02542, 2.59, 5.12913)   |

## Devir

| tezgah   |   n |   ort |   ss |   min |   maks | dagilim                        |
|:---------|----:|------:|-----:|------:|-------:|:-------------------------------|
| T01      |  30 | 84.96 | 6.13 |  74.2 |   96.6 | Lognormal(84.96, ss 6.13366)   |
| T02      |  30 | 86.1  | 6.87 |  73   |   98.6 | Lognormal(86.0967, ss 6.87467) |
| T03      |  30 | 85.47 | 6.24 |  72.4 |   97   | Normal(85.47, ss 6.23981)      |
| T04      |  30 | 85.17 | 5.93 |  72.5 |   96.1 | Normal(85.17, ss 5.93244)      |
| T05      |  30 | 84.32 | 6.69 |  70.7 |   99.1 | Lognormal(84.32, ss 6.68902)   |
| T06      |  30 | 85.39 | 7.6  |  71.9 |   98.4 | Normal(85.39, ss 7.59552)      |
| T07      |  30 | 83.9  | 5.81 |  74.1 |   99.3 | Lognormal(83.9033, ss 5.81464) |
| T08      |  30 | 85.59 | 5.41 |  75.1 |   94.7 | Normal(85.59, ss 5.40545)      |
| T09      |  30 | 86.93 | 5.85 |  72.9 |   96.6 | Normal(86.93, ss 5.85421)      |
| T10      |  30 | 87.34 | 4.97 |  75.9 |   97.3 | Lognormal(87.34, ss 4.96995)   |
| T11      |  30 | 84.97 | 6.06 |  74.9 |   96.4 | Lognormal(84.97, ss 6.06085)   |
| T12      |  30 | 87.44 | 6.37 |  74   |   99.3 | Normal(87.4367, ss 6.36816)    |
| T13      |  30 | 86.1  | 5.11 |  78.2 |   97   | Lognormal(86.0967, ss 5.11404) |
| T14      |  30 | 87.72 | 6    |  74.6 |   97.1 | Normal(87.7167, ss 6.00127)    |

## Doğrulama: iş örneklemesi

Model oranı (gercek) sahadaki %95 aralığın içinde mi?

| kaynak_tipi   | durum            |   oran |   alt |   ust |   gercek | aralikta   |
|:--------------|:-----------------|-------:|------:|------:|---------:|:-----------|
| halfe         | atki_kopusu      |  0.022 | 0.01  | 0.034 |    0.023 | True       |
| halfe         | ayar             |  0.022 | 0.011 | 0.033 |    0.015 | True       |
| halfe         | gozetim          |  0.595 | 0.505 | 0.686 |    0.658 | True       |
| halfe         | kisisel          |  0.046 | 0.029 | 0.063 |    0.049 | True       |
| halfe         | kontrol          |  0.108 | 0.076 | 0.14  |    0.108 | True       |
| halfe         | mola             |  0.176 | 0.066 | 0.287 |    0.125 | True       |
| halfe         | renk_degisimi    |  0.01  | 0.002 | 0.017 |    0.006 | True       |
| halfe         | top_indirme      |  0.021 | 0.011 | 0.03  |    0.016 | True       |
| telci         | besleme          |  0.056 | 0.034 | 0.077 |    0.054 | True       |
| telci         | cozgu_kopusu     |  0.063 | 0.045 | 0.082 |    0.077 | True       |
| telci         | gozetim          |  0.67  | 0.571 | 0.769 |    0.694 | True       |
| telci         | kisisel          |  0.038 | 0.022 | 0.054 |    0.05  | True       |
| telci         | mola             |  0.173 | 0.061 | 0.286 |    0.125 | True       |
| tezgah        | ariza            |  0.019 | 0.007 | 0.031 |    0.018 | True       |
| tezgah        | atki_kopusu      |  0.022 | 0.01  | 0.034 |    0.023 | True       |
| tezgah        | ayar             |  0.022 | 0.011 | 0.033 |    0.015 | True       |
| tezgah        | cozgu_degisimi   |  0.013 | 0.004 | 0.021 |    0.017 | True       |
| tezgah        | cozgu_kopusu     |  0.063 | 0.045 | 0.082 |    0.077 | True       |
| tezgah        | dokuma           |  0.686 | 0.622 | 0.75  |    0.702 | True       |
| tezgah        | personel_bekleme |  0.111 | 0.044 | 0.178 |    0.078 | True       |
| tezgah        | renk_degisimi    |  0.043 | 0.024 | 0.062 |    0.055 | True       |
| tezgah        | top_indirme      |  0.021 | 0.011 | 0.03  |    0.016 | True       |

## Doğrulama: m²/vardiya

| tezgah   |   saha_ort |   saha_n |   saha_ss |   model_ort |   fark_% |
|:---------|-----------:|---------:|----------:|------------:|---------:|
| T01      |      234.9 |       15 |      38   |       224.9 |     -4.2 |
| T02      |      202.1 |       15 |      18.5 |       178.3 |    -11.8 |
| T03      |      163   |       15 |      27.4 |       186.3 |     14.2 |
| T04      |      180.5 |       15 |      37.3 |       179.6 |     -0.5 |
| T05      |      182.6 |       15 |      24   |       180.6 |     -1.1 |
| T06      |      154.7 |       15 |      44.3 |       156.4 |      1.1 |
| T07      |      147.4 |       15 |      31.5 |       146.5 |     -0.6 |
| T08      |      156.8 |       15 |      33.3 |       153.4 |     -2.2 |
| T09      |      164.4 |       15 |      34.5 |       152.5 |     -7.2 |
| T10      |      157.2 |       15 |      28.8 |       156.5 |     -0.5 |
| T11      |      112.4 |       15 |      10   |       111.2 |     -1.1 |
| T12      |      149.3 |       15 |      21.5 |       155.1 |      3.9 |
| T13      |      194.3 |       15 |      26   |       184.7 |     -4.9 |
| T14      |      171.4 |       15 |      36.7 |       186.6 |      8.8 |

## Parametre kaynakları

| Parametre               | Değer                                                                                                                                                                      | Kaynak                                         |
|:------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------|
| yuz_sayisi              | 2                                                                                                                                                                          | VARSAYIM                                       |
| atki_sistemi            | 2                                                                                                                                                                          | VARSAYIM                                       |
| halfe_basina_tezgah     | 1                                                                                                                                                                          | FABRİKA                                        |
| telci_basina_tezgah     | 1                                                                                                                                                                          | FABRİKA                                        |
| is_rolleri              | (('atki_kopusu', 'halfe'), ('top_indirme', 'halfe'), ('ayar', 'halfe'), ('renk_degisimi', 'halfe'), ('kontrol', 'halfe'), ('cozgu_kopusu', 'telci'), ('besleme', 'telci')) | VARSAYIM                                       |
| top_uzunlugu            | Üçgen(20, 30, 40)                                                                                                                                                          | VARSAYIM                                       |
| renk_degisim_olasiligi  | 0.3                                                                                                                                                                        | VARSAYIM                                       |
| desen_degisim_olasiligi | 0.4                                                                                                                                                                        | VARSAYIM                                       |
| renk_ekibi              | 1                                                                                                                                                                          | VARSAYIM                                       |
| renk_ekip_payi          | 0.85                                                                                                                                                                       | FABRİKA ("büyük oranda"), oran VARSAYIM        |
| renk_degisim            | Üçgen(60, 90, 150)                                                                                                                                                         | VARSAYIM                                       |
| ayar                    | Üçgen(10.6931, 21.208, 41.784)                                                                                                                                             | ÖLÇÜM: zaman etüdü, Desen ayarı, n=54          |
| atki_kopus_saat         | 1.5277777777777777                                                                                                                                                         | ÖLÇÜM: kopuş kaydı n=1760                      |
| cozgu_kopus_saat        | 2.1015625                                                                                                                                                                  | ÖLÇÜM: kopuş kaydı n=2421                      |
| atki_mudahale           | Lognormal(1.24395, ss 0.396898)                                                                                                                                            | ÖLÇÜM: kopuş kaydı n=1760                      |
| cozgu_mudahale          | Üçgen(1.02542, 2.59, 5.12913)                                                                                                                                              | ÖLÇÜM: kopuş kaydı n=2421                      |
| top_indirme             | Lognormal(10.527, ss 1.94324)                                                                                                                                              | ÖLÇÜM: zaman etüdü, Top indirme, n=60          |
| besleme_aralik          | Üstel(ort 45)                                                                                                                                                              | VARSAYIM                                       |
| besleme_sure            | Lognormal(3.34684, ss 0.585729)                                                                                                                                            | ÖLÇÜM: zaman etüdü, Bobin/cağlık besleme, n=60 |
| kontrol_aralik          | Üstel(ort 30)                                                                                                                                                              | VARSAYIM                                       |
| kontrol_sure            | Üçgen(1.97749, 3.393, 7.99111)                                                                                                                                             | ÖLÇÜM: zaman etüdü, Halı kontrolü, n=60        |
| yurume_tezgah_arasi     | 0.15                                                                                                                                                                       | VARSAYIM                                       |
| yurume_sabit            | 0.1                                                                                                                                                                        | VARSAYIM                                       |
| secim_kurali            | oncelikli                                                                                                                                                                  | VARSAYIM                                       |
| ariza_mtbf_saat         | 40.0                                                                                                                                                                       | VARSAYIM                                       |
| ariza_onarim            | Üçgen(20, 45, 120)                                                                                                                                                         | VARSAYIM                                       |
| teknisyen_sayisi        | 2                                                                                                                                                                          | VARSAYIM                                       |
| cozgu_uzunlugu_m        | 600.0                                                                                                                                                                      | VARSAYIM                                       |
| cozgu_degisim           | Üçgen(120, 180, 300)                                                                                                                                                       | VARSAYIM                                       |
| cozgu_ekibi             | 1                                                                                                                                                                          | VARSAYIM                                       |
| vardiya_dk              | 480.0                                                                                                                                                                      | VARSAYIM                                       |
| molalar                 | ((120, 15), (240, 30), (360, 15))                                                                                                                                          | VARSAYIM                                       |
| mola_zamani             | toplu                                                                                                                                                                      | VARSAYIM                                       |
| mola_kapsama            | yok                                                                                                                                                                        | VARSAYIM                                       |
| yedek_sayisi            | 2                                                                                                                                                                          | VARSAYIM                                       |
| mola_dalga_sayisi       | 4                                                                                                                                                                          | VARSAYIM                                       |
| telci_yardim            | False                                                                                                                                                                      | VARSAYIM                                       |
| yardim_isleri           | ('atki_kopusu', 'kontrol')                                                                                                                                                 | VARSAYIM                                       |
| yorgunluk_orani         | 0.03                                                                                                                                                                       | VARSAYIM                                       |
| yorgunluk_tavan         | 0.25                                                                                                                                                                       | VARSAYIM                                       |
| yorgunluk_gece_ek       | 0.0                                                                                                                                                                        | VARSAYIM                                       |
| ogrenme_orani           | 0.8900958736259623                                                                                                                                                         | ÖLÇÜM: zaman etüdü, yeni personel n=281        |
| ogrenme_standart_tekrar | 998                                                                                                                                                                        | ÖLÇÜM: zaman etüdü, yeni personel n=281        |
| deneyim                 | ()                                                                                                                                                                         | VARSAYIM                                       |
| kisisel_aralik          | Üstel(ort 120)                                                                                                                                                             | VARSAYIM                                       |
| kisisel_sure            | Üçgen(3, 5, 10)                                                                                                                                                            | VARSAYIM                                       |
| sure_gun                | 7.0                                                                                                                                                                        | VARSAYIM                                       |
| isinma_dk               | 480.0                                                                                                                                                                      | VARSAYIM                                       |

| Tezgâh   | Marka                  |   Tarak (10 cm) |   En (m) |   Renk |   Tarak sayısı |   Sıra (10 cm) | Devir (/dk)                    |   Ort. m²/saat (kesintisiz) |   Kopuş çarpanı | Kaynak   | Sıra kaynağı   | Devir kaynağı             |
|:---------|:-----------------------|----------------:|---------:|-------:|---------------:|---------------:|:-------------------------------|----------------------------:|----------------:|:---------|:---------------|:--------------------------|
| T01      | Schönherr              |              42 |        5 |      8 |           2100 |             63 | Lognormal(84.96, ss 6.13366)   |                        40.5 |           1.05  | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T02      | Van De Wiele           |              42 |        4 |      7 |           1680 |             63 | Lognormal(86.0967, ss 6.87467) |                        32.8 |           1     | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T03      | Van De Wiele           |              42 |        4 |      7 |           1716 |             63 | Normal(85.47, ss 6.23981)      |                        32.6 |           1     | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T04      | Van De Wiele           |              42 |        4 |      7 |           1716 |             63 | Normal(85.17, ss 5.93244)      |                        32.4 |           1     | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T05      | Van De Wiele           |              42 |        4 |      7 |           1680 |             63 | Lognormal(84.32, ss 6.68902)   |                        32.1 |           1     | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T06      | Schönherr              |              50 |        4 |      6 |           2000 |             75 | Normal(85.39, ss 7.59552)      |                        27.3 |           0.982 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T07      | Schönherr              |              50 |        4 |      8 |           2000 |             75 | Lognormal(83.9033, ss 5.81464) |                        26.8 |           1.082 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T08      | Schönherr              |              50 |        4 |      8 |           2000 |             75 | Normal(85.59, ss 5.40545)      |                        27.4 |           1.082 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T09      | Van De Wiele-Schönherr |              50 |        4 |      8 |           2000 |             75 | Normal(86.93, ss 5.85421)      |                        27.8 |           1.082 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T10      | Van De Wiele           |              50 |        4 |      8 |           2020 |             75 | Lognormal(87.34, ss 4.96995)   |                        27.9 |           1.082 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T11      | Schönherr              |              70 |        4 |      8 |           2800 |            105 | Lognormal(84.97, ss 6.06085)   |                        19.4 |           1.162 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T12      | Van De Wiele           |              50 |        4 |      8 |           2000 |             75 | Normal(87.4367, ss 6.36816)    |                        28   |           1.082 | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T13      | Van De Wiele           |              42 |        4 |      7 |           1680 |             63 | Lognormal(86.0967, ss 5.11404) |                        32.8 |           1     | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
| T14      | Van De Wiele           |              42 |        4 |      7 |           1680 |             63 | Normal(87.7167, ss 6.00127)    |                        33.4 |           1     | FABRİKA  | VARSAYIM       | ÖLÇÜM: devir okuması n=30 |
