# SimPy Üretim Hattı Simülasyonu

Python ve SimPy ile seri bir üretim hattının ayrık olay simülasyonu. Amaç: "hatta bir operatör ya da tampon eklersem çıktı ne kadar artar?" sorusuna istatistiksel olarak cevap vermek.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Durum

- [x] Hafta 1: M/M/1 doğrulandı (`src/mm1.py`, `tests/test_mm1.py`)
- [ ] Hafta 2: Seri hat modeli ve metrikler (`src/hat.py`, `src/istatistik.py`)
- [ ] Hafta 3: Deney ve what-if analizi (`src/deney.py`, S0-S3)
- [ ] Hafta 4: Streamlit paneli (`app/panel.py`)

## Hafta 1: M/M/1 doğrulaması

```bash
python -m src.mm1_dogrulama   # tabloyu üretir: results/mm1_dogrulama.{csv,md}
pytest                         # hızlı testler (~30 sn)
```

μ = 1, ortak taban tohum 1000 (replikasyon i için tohum = 1000 + i). W_q ısınma sonrası gelen müşterilerin ortalama bekleme süresi, L_q ısınma sonrası zaman ağırlıklı ortalama kuyruk uzunluğudur.

| λ | ρ | Rep. | Koşu / ısınma | Teorik W_q | Sim. W_q (±%95 YG) | Sapma | Teorik L_q | Sim. L_q (±%95 YG) | Sapma |
|---|---|---|---|---|---|---|---|---|---|
| 0,5 | 0,5 | 30 | 100.000 / 5.000 | 1,0 | 0,999 ± 0,009 | -0,07% | 0,5 | 0,500 ± 0,005 | -0,08% |
| 0,8 | 0,8 | 30 | 200.000 / 10.000 | 4,0 | 4,007 ± 0,038 | +0,17% | 3,2 | 3,207 ± 0,032 | +0,23% |
| 0,9 | 0,9 | 50 | 500.000 / 20.000 | 9,0 | 9,017 ± 0,064 | +0,18% | 8,1 | 8,115 ± 0,059 | +0,19% |

Üç satırın da sapması %3 hedefinin çok altında; teorik değerler her satırda %95 güven aralığının içinde. Little yasası (L_q = λ·W_q) farkı en fazla %0,06.

## Klasör yapısı

```text
src/
  mm1.py            # Model 1: tek istasyon
  mm1_dogrulama.py  # Bölüm 6 doğrulama tablosu
  analiz.py         # güven aralığı
tests/
  test_mm1.py
results/            # üretilen tablolar
data/               # gerçek veri (git'e eklenmez)
```
