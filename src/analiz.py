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
