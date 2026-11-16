"""Veri toplama ve özet metrikler.

Tüm kaydediciler ısınma süresinden önceki zamanı atar: ölçüm penceresi
[isinma, bitis] aralığıdır.
"""
from __future__ import annotations

DURUMLAR = ("calisma", "bos", "bloklu", "ariza")


class DurumKaydedici:
    """Bir sunucunun (makine/operatör) durumlarında geçen süreyi tutar.

    Arıza her zaman önceliklidir: makine arızalıyken alttaki durum ne olursa
    olsun süre "ariza" hanesine yazılır.
    """

    def __init__(self, env, isinma: float):
        self.env = env
        self.isinma = isinma
        self.alt_durum = "bos"
        self.arizali = False
        self.son_t = 0.0
        self.sure = {d: 0.0 for d in DURUMLAR}

    @property
    def etkin(self) -> str:
        return "ariza" if self.arizali else self.alt_durum

    def _kapat(self) -> None:
        t = self.env.now
        bas = max(self.son_t, self.isinma)
        if t > bas:
            self.sure[self.etkin] += t - bas
        self.son_t = t

    def durum(self, yeni: str) -> None:
        self._kapat()
        self.alt_durum = yeni

    def ariza(self, var: bool) -> None:
        self._kapat()
        self.arizali = var

    def oranlar(self) -> dict:
        self._kapat()
        toplam = sum(self.sure.values())
        return {d: (v / toplam if toplam else 0.0) for d, v in self.sure.items()}


class SeviyeKaydedici:
    """Bir sayacın (ara stok seviyesi, WIP) zaman ağırlıklı ortalaması ve maksimumu."""

    def __init__(self, env, isinma: float):
        self.env = env
        self.isinma = isinma
        self.seviye = 0
        self.son_t = 0.0
        self.alan = 0.0
        self.maks = 0

    def degistir(self, delta: int) -> None:
        t = self.env.now
        bas = max(self.son_t, self.isinma)
        if t > bas:
            self.alan += self.seviye * (t - bas)
        self.son_t = t
        self.seviye += delta
        if t >= self.isinma:
            self.maks = max(self.maks, self.seviye)

    def ortalama(self, bitis: float) -> float:
        self.degistir(0)
        pencere = bitis - self.isinma
        return self.alan / pencere if pencere > 0 else 0.0
