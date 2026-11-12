"""Model 1: M/M/1 kuyruk modeli (doğrulama referansı).

Tek sunuculu, Poisson varışlı (hız λ) ve üstel işlem süreli (hız μ) sistem.
Simülasyon sonuçları teorik W_q ve L_q değerleriyle karşılaştırılır.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import simpy


@dataclass(frozen=True)
class MM1Parametre:
    lam: float = 0.5          # varış hızı λ
    mu: float = 1.0           # servis hızı μ
    sure: float = 100_000.0   # toplam koşu süresi (ısınma dahil)
    isinma: float = 5_000.0   # atılacak ısınma süresi


def teorik(lam: float, mu: float) -> dict:
    """M/M/1 teorik değerleri (ρ < 1 olmalı)."""
    rho = lam / mu
    if rho >= 1:
        raise ValueError("Kararlılık için ρ = λ/μ < 1 olmalı")
    return {
        "rho": rho,
        "Wq": rho / (mu * (1 - rho)),
        "Lq": rho**2 / (1 - rho),
        "W": 1 / (mu - lam),
        "L": rho / (1 - rho),
    }


class _KuyrukIzleyici:
    """Kuyruk uzunluğunun zaman ağırlıklı alanını ısınma sonrası için tutar."""

    def __init__(self, env: simpy.Environment, isinma: float):
        self.env = env
        self.isinma = isinma
        self.n = 0
        self.son_t = 0.0
        self.alan = 0.0

    def degistir(self, delta: int) -> None:
        t = self.env.now
        bas = max(self.son_t, self.isinma)
        if t > bas:
            self.alan += self.n * (t - bas)
        self.son_t = t
        self.n += delta

    def ortalama(self, bitis: float) -> float:
        self.degistir(0)  # alanı bitiş anına kadar kapat
        return self.alan / (bitis - self.isinma)


def _musteri(env, sunucu, mu, rng, kayit, izleyici):
    gelis = env.now
    izleyici.degistir(+1)
    with sunucu.request() as istek:
        yield istek                                   # sırada bekle
        izleyici.degistir(-1)
        bekleme = env.now - gelis
        yield env.timeout(rng.exponential(1 / mu))    # işlem süresi
    kayit.append((gelis, bekleme))


def _varis_sureci(env, sunucu, lam, mu, rng, kayit, izleyici):
    while True:
        yield env.timeout(rng.exponential(1 / lam))   # varışlar arası süre
        env.process(_musteri(env, sunucu, mu, rng, kayit, izleyici))


def kos(p: MM1Parametre, seed: int) -> dict:
    """Tek replikasyon. Isınma sonrası gelen müşteriler için ortalama W_q
    ve ısınma sonrası zaman ağırlıklı ortalama L_q döndürür."""
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    sunucu = simpy.Resource(env, capacity=1)
    kayit: list[tuple[float, float]] = []
    izleyici = _KuyrukIzleyici(env, p.isinma)
    env.process(_varis_sureci(env, sunucu, p.lam, p.mu, rng, kayit, izleyici))
    env.run(until=p.sure)

    bekleme = np.array([b for (g, b) in kayit if g >= p.isinma])
    return {
        "seed": seed,
        "Wq": float(bekleme.mean()),
        "Lq": izleyici.ortalama(p.sure),
        "n_musteri": int(bekleme.size),
    }


def replikasyonlar(p: MM1Parametre, n: int = 30, taban_seed: int = 1000) -> list[dict]:
    """n bağımsız replikasyon; replikasyon i için tohum = taban + i."""
    return [kos(p, taban_seed + i) for i in range(n)]
