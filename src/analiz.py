"""Güven aralığı ve karşılaştırma yardımcıları."""
from __future__ import annotations

import numpy as np
from scipy import stats


def guven_araligi(x, guven: float = 0.95) -> tuple[float, float]:
    """Replikasyon ortalamaları için t tabanlı (ortalama, yarı genişlik)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    ort = float(x.mean())
    if n < 2:
        return ort, float("nan")
    s = x.std(ddof=1)
    t = stats.t.ppf(0.5 + guven / 2, n - 1)
    return ort, float(t * s / np.sqrt(n))


def eslestirilmis_fark(x, y, guven: float = 0.95) -> dict:
    """Ortak rastgele sayılarla koşulmuş iki senaryo için eşleştirilmiş t aralığı.

    Fark y - x üzerinden hesaplanır. Aralık sıfırı içermiyorsa fark anlamlıdır.
    """
    d = np.asarray(y, dtype=float) - np.asarray(x, dtype=float)
    ort, yg = guven_araligi(d, guven)
    return {"fark": ort, "yg": yg, "alt": ort - yg, "ust": ort + yg,
            "anlamli": bool(ort - yg > 0 or ort + yg < 0)}


def bicimle(ort: float, yg: float, basamak: int = 2) -> str:
    return f"{ort:.{basamak}f} ± {yg:.{basamak}f}"


def hareketli_ortalama(x, w: int) -> np.ndarray:
    """Welch yöntemindeki hareketli ortalama: i < w için pencere 2i+1, sonra 2w+1."""
    x = np.asarray(x, dtype=float)
    m = x.size - w
    sonuc = np.empty(m)
    for i in range(m):
        k = min(i, w)
        sonuc[i] = x[i - k:i + k + 1].mean()
    return sonuc
