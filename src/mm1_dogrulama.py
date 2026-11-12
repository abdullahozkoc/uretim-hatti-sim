"""M/M/1 doğrulama tablosu (Bölüm 6).

Çalıştırma:  python -m src.mm1_dogrulama
Çıktı:       results/mm1_dogrulama.csv ve results/mm1_dogrulama.md
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from src.analiz import guven_araligi
from src.mm1 import MM1Parametre, kos, teorik

# Yüksek ρ'da yakınsama yavaş: koşu uzunluğu ve replikasyon sayısı artırıldı.
DENEYLER = [
    # (λ, koşu süresi, ısınma, replikasyon sayısı)
    (0.5, 100_000, 5_000, 30),
    (0.8, 200_000, 10_000, 30),
    (0.9, 500_000, 20_000, 50),
]
MU = 1.0
TABAN_SEED = 1000
TOLERANS = 0.03  # %3


def _kos(args):
    p, seed = args
    return kos(p, seed)


def tablo_uret() -> pd.DataFrame:
    satirlar = []
    with ProcessPoolExecutor() as havuz:
        for lam, sure, isinma, n in DENEYLER:
            p = MM1Parametre(lam=lam, mu=MU, sure=sure, isinma=isinma)
            sonuc = list(havuz.map(_kos, [(p, TABAN_SEED + i) for i in range(n)]))
            th = teorik(lam, MU)
            wq, wq_yg = guven_araligi([r["Wq"] for r in sonuc])
            lq, lq_yg = guven_araligi([r["Lq"] for r in sonuc])
            satirlar.append({
                "λ": lam, "ρ": th["rho"], "Replikasyon": n, "Koşu süresi": sure, "Isınma": isinma,
                "Teorik W_q": th["Wq"], "Sim W_q": wq, "W_q %95 YG ±": wq_yg,
                "W_q sapma (%)": 100 * (wq - th["Wq"]) / th["Wq"],
                "Teorik L_q": th["Lq"], "Sim L_q": lq, "L_q %95 YG ±": lq_yg,
                "L_q sapma (%)": 100 * (lq - th["Lq"]) / th["Lq"],
                # Little yasası kontrolü: L_q ≈ λ·W_q
                "Little farkı (%)": 100 * (lq - lam * wq) / (lam * wq),
            })
    return pd.DataFrame(satirlar)


def main() -> None:
    df = tablo_uret()
    cikti = Path(__file__).resolve().parent.parent / "results"
    cikti.mkdir(exist_ok=True)
    df.to_csv(cikti / "mm1_dogrulama.csv", index=False)
    (cikti / "mm1_dogrulama.md").write_text(df.round(3).to_markdown(index=False) + "\n")
    print(df.round(3).to_string(index=False))
    gecti = (df["W_q sapma (%)"].abs() < 100 * TOLERANS).all() and \
            (df["L_q sapma (%)"].abs() < 100 * TOLERANS).all()
    print("\nSONUÇ:", "GEÇTİ" if gecti else "KALDI", f"(tolerans %{100*TOLERANS:.0f})")


if __name__ == "__main__":
    main()
