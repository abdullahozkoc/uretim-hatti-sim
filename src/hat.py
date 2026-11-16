"""Model 2: Seri üretim hattı.

İş parçaları istasyonları sırayla gezer. İstasyon i ile i+1 arasında
kapasitesi sınırlı bir ara stok (simpy.Store) vardır. Ara stok doluysa
istasyon, işlediği parçayı elinde tutarak bekler (bloklanma, BAS kuralı);
ara stok boşsa sonraki istasyon parça bekler (açlık). İlk istasyonun önünde
sınırsız hammadde vardır, son istasyon parçayı doğrudan hattan çıkarır.

Her istasyon `kapasite` adet paralel sunucudan (makine/operatör) oluşur;
her sunucunun kendi arıza süreci vardır: üstel dağılımlı MTBF (takvim zamanı)
sonrası makine durur, üstel dağılımlı MTTR kadar onarılır. Arıza işlem
sırasında gelirse kalan işlem süresi onarımdan sonra tamamlanır.

Rastgele sayılar: replikasyon tohumundan `SeedSequence` ile her sunucu için
ayrı işlem ve arıza akışları türetilir. Böylece senaryolar arasında ortak
rastgele sayılar (CRN) daha iyi eşleşir ve sonuç aynı tohumla birebir tekrarlanır.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np
import pandas as pd
import simpy

from src.istatistik import DurumKaydedici, SeviyeKaydedici

ALT_SINIR = 0.1  # normal dağılım örnekleri için alt sınır (dk)


@dataclass(frozen=True)
class IstasyonParam:
    ad: str
    ort: float                          # ortalama işlem süresi (dk)
    dagilim: str = "normal"             # normal | ucgen | ustel | sabit
    sigma: float = 0.3                  # normal için standart sapma
    ucgen: Optional[tuple] = None       # (en küçük, tepe, en büyük)
    mtbf: Optional[float] = None        # None: arıza yok
    mttr: float = 0.0
    kapasite: int = 1                   # paralel sunucu sayısı
    tampon: Optional[int] = 5           # sonraki ara stok kapasitesi (son istasyonda yok sayılır)

    def ornek(self, rng: np.random.Generator) -> float:
        if self.dagilim == "normal":
            return max(ALT_SINIR, rng.normal(self.ort, self.sigma))
        if self.dagilim == "ucgen":
            a, m, b = self.ucgen
            return rng.triangular(a, m, b)
        if self.dagilim == "ustel":
            return rng.exponential(self.ort)
        if self.dagilim == "sabit":
            return self.ort
        raise ValueError(f"Bilinmeyen dağılım: {self.dagilim}")

    @property
    def ortalama_sure(self) -> float:
        """Dağılımın gerçek ortalaması (üçgende (a+m+b)/3)."""
        if self.dagilim == "ucgen":
            return sum(self.ucgen) / 3
        return self.ort


@dataclass(frozen=True)
class HatParam:
    istasyonlar: tuple
    sure: float = 5_000.0       # ölçüm süresi (ısınma hariç), dk
    isinma: float = 500.0       # atılan ısınma süresi, dk
    ariza: bool = True          # False: tüm arızalar kapatılır
    dilim: float = 10.0         # zaman serisi dilim genişliği, dk
    gunluk: bool = False        # olay günlüğü (kısa koşular için)

    @property
    def bitis(self) -> float:
        return self.isinma + self.sure

    def istasyon_degistir(self, indeks: int, **degisiklik) -> "HatParam":
        ist = list(self.istasyonlar)
        ist[indeks] = replace(ist[indeks], **degisiklik)
        return replace(self, istasyonlar=tuple(ist))

    def tum_tamponlar(self, k: int) -> "HatParam":
        return replace(self, istasyonlar=tuple(replace(s, tampon=k) for s in self.istasyonlar))


def temel_hat(**kw) -> HatParam:
    """Dokümanın Bölüm 7 tablosundaki başlangıç parametreleri (S0)."""
    return HatParam(istasyonlar=(
        IstasyonParam("İstasyon 1", 2.0, "normal", 0.3, mtbf=240, mttr=15),
        IstasyonParam("İstasyon 2", 2.2, "normal", 0.3, mtbf=300, mttr=20),
        IstasyonParam("İstasyon 3", 2.6, "ucgen", ucgen=(2.0, 2.6, 3.4), mtbf=180, mttr=25),
        IstasyonParam("İstasyon 4", 2.1, "normal", 0.3, mtbf=360, mttr=10),
        IstasyonParam("İstasyon 5", 1.9, "normal", 0.2, mtbf=400, mttr=10, tampon=None),
    ), **kw)


@dataclass
class HatSonuc:
    ozet: dict                  # tek değerli metrikler
    istasyon: pd.DataFrame      # istasyon başına durum oranları
    tampon: pd.DataFrame        # ara stok doluluğu
    zaman_serisi: pd.DataFrame  # dilim başına çıkış ve ara stok seviyeleri (ısınma dahil)
    gunluk: Optional[pd.DataFrame] = None


class _Parca:
    __slots__ = ("no", "giris")

    def __init__(self, no: int, giris: float):
        self.no = no
        self.giris = giris


class _Sunucu:
    def __init__(self, hat: "_Hat", ist_no: int, sira: int, islem_rng, ariza_rng):
        self.hat = hat
        self.env = hat.env
        self.ist_no = ist_no
        self.ad = f"{hat.p.istasyonlar[ist_no].ad}/{sira + 1}"
        self.par = hat.p.istasyonlar[ist_no]
        self.islem_rng = islem_rng
        self.ariza_rng = ariza_rng
        self.kayit = DurumKaydedici(self.env, hat.p.isinma)
        self.arizali = False
        self.tamir = None
        self.proc = self.env.process(self._calis())
        if hat.p.ariza and self.par.mtbf:
            self.env.process(self._ariza())

    def _calis(self):
        env, hat, i = self.env, self.hat, self.ist_no
        giris_st = hat.tamponlar[i - 1] if i > 0 else None
        cikis_st = hat.tamponlar[i] if i < len(hat.tamponlar) else None
        while True:
            self.kayit.durum("bos")
            if giris_st is None:            # sınırsız hammadde
                parca = hat.yeni_parca()
            else:
                parca = yield giris_st.get()
                hat.tampon_kayit[i - 1].degistir(-1)
            hat.olay(self.ad, "baslangic", parca.no)
            kalan = self.par.ornek(self.islem_rng)
            self.kayit.durum("calisma")  # arızalıyken süre önceliğe göre "ariza"ya yazılır
            while kalan > 1e-12:
                bas = None
                try:
                    if self.arizali:
                        yield self.tamir
                        continue
                    bas = env.now
                    yield env.timeout(kalan)
                    kalan = 0.0
                except simpy.Interrupt:
                    if bas is not None:
                        kalan -= env.now - bas
            hat.olay(self.ad, "bitis", parca.no)
            if cikis_st is None:
                hat.cikis(parca)
            else:
                self.kayit.durum("bloklu")
                yield cikis_st.put(parca)
                hat.tampon_kayit[i].degistir(+1)

    def _ariza(self):
        env = self.env
        while True:
            yield env.timeout(self.ariza_rng.exponential(self.par.mtbf))
            self.arizali = True
            self.tamir = env.event()
            self.kayit.ariza(True)
            self.hat.olay(self.ad, "ariza", None)
            if self.kayit.alt_durum == "calisma" and not self.proc.triggered:
                self.proc.interrupt()
            yield env.timeout(self.ariza_rng.exponential(self.par.mttr) if self.par.mttr else 0)
            self.arizali = False
            self.kayit.ariza(False)
            self.hat.olay(self.ad, "onarim", None)
            self.tamir.succeed()


class _Hat:
    def __init__(self, p: HatParam, seed: int):
        self.p = p
        self.env = simpy.Environment()
        n = len(p.istasyonlar)
        # Son istasyon dışındaki her istasyonun ardında bir ara stok var.
        self.tamponlar = [simpy.Store(self.env, capacity=s.tampon if s.tampon else float("inf"))
                          for s in p.istasyonlar[:-1]]
        self.tampon_kayit = [SeviyeKaydedici(self.env, p.isinma) for _ in self.tamponlar]
        self.wip = SeviyeKaydedici(self.env, p.isinma)
        self.giren = 0
        self.cikan = 0                   # toplam (ısınma dahil)
        self.cevrim: list[float] = []    # ısınma sonrası çıkanlar için
        self.cikis_zamanlari: list[float] = []
        self._gunluk = [] if p.gunluk else None

        ss = np.random.SeedSequence(seed)
        cocuk = ss.spawn(n)
        self.sunucular: list[_Sunucu] = []
        for i, ist in enumerate(p.istasyonlar):
            akislar = cocuk[i].spawn(2 * ist.kapasite)
            for k in range(ist.kapasite):
                self.sunucular.append(_Sunucu(self, i, k,
                                              np.random.default_rng(akislar[2 * k]),
                                              np.random.default_rng(akislar[2 * k + 1])))

    def yeni_parca(self) -> _Parca:
        self.giren += 1
        self.wip.degistir(+1)
        return _Parca(self.giren, self.env.now)

    def cikis(self, parca: _Parca) -> None:
        self.cikan += 1
        self.wip.degistir(-1)
        self.cikis_zamanlari.append(self.env.now)
        if self.env.now >= self.p.isinma:
            self.cevrim.append(self.env.now - parca.giris)

    def olay(self, kaynak, tur, parca_no) -> None:
        if self._gunluk is not None:
            self._gunluk.append((self.env.now, kaynak, tur, parca_no))


def kos(p: HatParam, seed: int) -> HatSonuc:
    """Tek replikasyon: parametre + tohum -> metrik tabloları (saf fonksiyon)."""
    hat = _Hat(p, seed)

    # Zaman serisi için dilim örnekleyici
    seri = []

    def ornekleyici():
        onceki = 0
        while True:
            yield hat.env.timeout(p.dilim)
            seri.append({"t": hat.env.now, "cikis": hat.cikan - onceki,
                         "wip": hat.wip.seviye,
                         **{f"tampon_{j + 1}": len(s.items) for j, s in enumerate(hat.tamponlar)}})
            onceki = hat.cikan

    hat.env.process(ornekleyici())
    hat.env.run(until=p.bitis)

    # İstasyon tablosu: aynı istasyondaki sunucuların ortalaması
    satirlar = []
    for i, ist in enumerate(p.istasyonlar):
        oranlar = [s.kayit.oranlar() for s in hat.sunucular if s.ist_no == i]
        ort = {d: float(np.mean([o[d] for o in oranlar])) for d in oranlar[0]}
        satirlar.append({"istasyon": ist.ad, "kapasite": ist.kapasite, **ort,
                         "kullanim": ort["calisma"] + ort["ariza"]})
    istasyon = pd.DataFrame(satirlar)

    tampon = pd.DataFrame([{
        "tampon": f"{p.istasyonlar[j].ad} → {p.istasyonlar[j + 1].ad}",
        "kapasite": p.istasyonlar[j].tampon,
        "ortalama": k.ortalama(p.bitis), "maksimum": k.maks,
    } for j, k in enumerate(hat.tampon_kayit)])

    # Darboğaz: kullanımı en yüksek istasyon; eşitlikte önünde en uzun kuyruk biriken.
    istasyon["onundeki_kuyruk"] = [0.0] + list(tampon["ortalama"]) if len(tampon) else [0.0]
    sira = istasyon.assign(_k=istasyon["kullanim"].round(3)).sort_values(
        ["_k", "onundeki_kuyruk"], ascending=False)
    darbogaz = sira.iloc[0]["istasyon"]

    cikan_pencere = len(hat.cevrim)
    verim = cikan_pencere / p.sure * 60          # ürün/saat
    cevrim = float(np.mean(hat.cevrim)) if hat.cevrim else float("nan")
    wip = hat.wip.ortalama(p.bitis)
    ozet = {
        "seed": seed,
        "verim": verim,
        "cevrim_suresi": cevrim,
        "wip": wip,
        "tampon_wip": float(tampon["ortalama"].sum()) if len(tampon) else 0.0,
        "darbogaz": darbogaz,
        "giren": hat.giren,
        "cikan": hat.cikan,
        "sistemde": hat.wip.seviye,
        "little_farki": (wip - verim / 60 * cevrim) / wip if wip else float("nan"),
    }
    gunluk = (pd.DataFrame(hat._gunluk, columns=["t", "kaynak", "olay", "parca"])
              if hat._gunluk is not None else None)
    return HatSonuc(ozet, istasyon, tampon, pd.DataFrame(seri), gunluk)
