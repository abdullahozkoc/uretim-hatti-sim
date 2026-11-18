"""Halı dokuma salonu parametreleri.

Bütün sayılar tek yerde durur ve her birinin bir `kaynak` etiketi vardır:
"VARSAYIM" (henüz ölçülmedi) ya da "ÖLÇÜM: ..." (iş etüdünden geldi).
Varsayılan değerler yüz yüze (çift yüzlü) jakar halı tezgâhı için makul
tahminlerdir; fabrika verisi değildir. Ölçüm geldikçe `src.hali.is_etudu`
fonksiyonları ya da JSON dosyası (`data/hali/parametreler.json`) ile değiştirilir.

Birimler: süreler dakika, kopuş ve arıza sıklıkları *dokuma saati* başına,
uzunluklar metre.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

import numpy as np

VARSAYIM = "VARSAYIM"


# --------------------------------------------------------------------- dağılım
@dataclass(frozen=True)
class Dagilim:
    """Rastgele süre/uzunluk. tip: sabit | ucgen | ustel | normal | lognormal | ampirik.

    sabit: a=değer · ucgen: (a=min, b=en olası, c=maks) · ustel: a=ortalama
    normal / lognormal: a=ortalama, b=standart sapma · ampirik: veri listesinden çekiliş
    """
    tip: str
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    veri: tuple = ()
    kaynak: str = VARSAYIM

    def ornek(self, rng: np.random.Generator) -> float:
        t = self.tip
        if t == "sabit":
            return self.a
        if t == "ucgen":
            return float(rng.triangular(self.a, self.b, self.c)) if self.c > self.a else self.a
        if t == "ustel":
            return float(rng.exponential(self.a))
        if t == "normal":
            return max(0.0, float(rng.normal(self.a, self.b)))
        if t == "lognormal":
            s2 = np.log(1 + (self.b / self.a) ** 2)
            return float(rng.lognormal(np.log(self.a) - s2 / 2, np.sqrt(s2)))
        if t == "ampirik":
            return float(self.veri[rng.integers(len(self.veri))])
        raise ValueError(f"Bilinmeyen dağılım tipi: {t}")

    @property
    def ortalama(self) -> float:
        if self.tip == "ucgen":
            return (self.a + self.b + self.c) / 3
        if self.tip == "ampirik":
            return float(np.mean(self.veri))
        return self.a

    def olcekle(self, k: float) -> "Dagilim":
        """Süreyi k katına çıkarır (ör. SMED ile %40 kısalma: k=0.6)."""
        return replace(self, a=self.a * k, b=self.b * k, c=self.c * k,
                       veri=tuple(v * k for v in self.veri))

    def __str__(self) -> str:
        if self.tip == "ucgen":
            return f"Üçgen({self.a:g}, {self.b:g}, {self.c:g})"
        if self.tip == "ustel":
            return f"Üstel(ort {self.a:g})"
        if self.tip in ("normal", "lognormal"):
            return f"{self.tip.capitalize()}({self.a:g}, ss {self.b:g})"
        if self.tip == "ampirik":
            return f"Ampirik(n={len(self.veri)}, ort {self.ortalama:.2f})"
        return f"Sabit({self.a:g})"


def ucgen(mn, md, mx, kaynak=VARSAYIM) -> Dagilim:
    return Dagilim("ucgen", mn, md, mx, kaynak=kaynak)


def ustel(ort, kaynak=VARSAYIM) -> Dagilim:
    return Dagilim("ustel", ort, kaynak=kaynak)


def sabit(x, kaynak=VARSAYIM) -> Dagilim:
    return Dagilim("sabit", x, kaynak=kaynak)


# ----------------------------------------------------------------------- ürün
@dataclass(frozen=True)
class Urun:
    """Bir halı kalitesi/deseni. `oran` sipariş karmasındaki payıdır."""
    ad: str
    oran: float
    atki_sikligi: float            # atkı / metre (halı boyu)
    en_m: float = 4.0              # dokuma eni
    kopus_carpani: float = 1.0     # kopuş sıklığını bu kaliteye göre ölçekler
    top_uzunlugu: Dagilim = field(default_factory=lambda: ucgen(20, 30, 40))
    kaynak: str = VARSAYIM


def _varsayilan_urunler() -> tuple[Urun, ...]:
    return (
        Urun("A (seyrek, 1.000 sık)", 0.5, 2_000, kopus_carpani=0.8),
        Urun("B (orta, 1.250 sık)", 0.3, 2_500, kopus_carpani=1.0),
        Urun("C (sık, 1.500 sık)", 0.2, 3_000, kopus_carpani=1.4),
    )


# ------------------------------------------------------------------- parametre
@dataclass(frozen=True)
class HaliParam:
    # Salon ve tezgâh
    tezgah_sayisi: int = 12
    operator_basina_tezgah: int = 4          # ardışık tezgâhlar bir operatöre atanır
    devir: float = 100.0                     # atkı / dk (tezgâh hızı)
    yuz_sayisi: int = 2                      # yüz yüze tezgâh aynı anda 2 halı dokur
    urunler: tuple[Urun, ...] = field(default_factory=_varsayilan_urunler)

    # Kopuşlar (dokuma saati başına ortalama sayı; üstel aralıklar)
    atki_kopus_saat: float = 1.5
    cozgu_kopus_saat: float = 0.8
    atki_mudahale: Dagilim = field(default_factory=lambda: ucgen(0.5, 1.0, 2.0))
    cozgu_mudahale: Dagilim = field(default_factory=lambda: ucgen(1.0, 2.5, 5.0))

    # Operatör işleri
    top_indirme: Dagilim = field(default_factory=lambda: ucgen(6, 10, 15))
    ayar: Dagilim = field(default_factory=lambda: ucgen(20, 35, 60))      # ürün/renk değişimi
    besleme_aralik: Dagilim = field(default_factory=lambda: ustel(60))    # dokuma dk; tezgâhı durdurmaz
    besleme_sure: Dagilim = field(default_factory=lambda: ucgen(2, 3, 5))
    yurume_tezgah_arasi: float = 0.15        # dk / tezgâh aralığı
    yurume_sabit: float = 0.10               # her yürüyüşte sabit pay (dk)
    secim_kurali: str = "fifo"               # fifo | en_yakin

    # Arıza ve bakım (teknisyen havuzu)
    ariza_mtbf_saat: float = 40.0            # dokuma saati
    ariza_onarim: Dagilim = field(default_factory=lambda: ucgen(20, 45, 120))
    teknisyen_sayisi: int = 1

    # Çözgü (çözgü ekibi değiştirir)
    cozgu_uzunlugu_m: float = 600.0
    cozgu_degisim: Dagilim = field(default_factory=lambda: ucgen(120, 180, 300))
    cozgu_ekibi: int = 1

    # Vardiya, mola, kişisel ihtiyaç
    vardiya_dk: float = 480.0
    molalar: tuple[tuple[float, float], ...] = ((120, 15), (240, 30), (360, 15))  # (vardiya içi başlangıç, süre)
    mola_duzeni: str = "toplu"               # toplu | kademeli | yedek
    kisisel_aralik: Dagilim = field(default_factory=lambda: ustel(120))
    kisisel_sure: Dagilim = field(default_factory=lambda: ucgen(3, 5, 10))

    # Koşu
    sure_gun: float = 7.0                    # ısınma hariç ölçüm süresi
    isinma_dk: float = 480.0

    # Parametre kaynakları (skaler alanlar için; dağılımlar kendi etiketini taşır)
    kaynaklar: tuple[tuple[str, str], ...] = ()

    # ----------------------------------------------------------- türetilenler
    @property
    def operator_sayisi(self) -> int:
        return -(-self.tezgah_sayisi // self.operator_basina_tezgah)

    @property
    def bitis_dk(self) -> float:
        return self.isinma_dk + self.sure_gun * 1440

    def kaynak(self, alan: str) -> str:
        d = dict(self.kaynaklar)
        if alan in d:
            return d[alan]
        deger = getattr(self, alan)
        return deger.kaynak if isinstance(deger, Dagilim) else VARSAYIM

    def olcum_ile(self, alan: str, deger, aciklama: str) -> "HaliParam":
        """Bir alanı ölçülmüş değerle değiştirir ve kaynağını işaretler."""
        etiket = f"ÖLÇÜM: {aciklama}"
        if isinstance(deger, Dagilim):
            deger = replace(deger, kaynak=etiket)
        k = dict(self.kaynaklar)
        k[alan] = etiket
        return replace(self, **{alan: deger}, kaynaklar=tuple(k.items()))

    def tablo(self):
        """Parametre, değer ve kaynak tablosu (rapor ve panel için)."""
        import pandas as pd
        satirlar = []
        for f in fields(self):
            if f.name in ("kaynaklar", "urunler"):
                continue
            v = getattr(self, f.name)
            satirlar.append({"Parametre": f.name, "Değer": str(v), "Kaynak": self.kaynak(f.name)})
        for u in self.urunler:
            satirlar.append({"Parametre": f"ürün: {u.ad}",
                             "Değer": f"pay %{100 * u.oran:.0f}, {u.atki_sikligi:g} atkı/m, en {u.en_m:g} m, "
                                      f"kopuş ×{u.kopus_carpani:g}, top {u.top_uzunlugu}",
                             "Kaynak": u.kaynak})
        return pd.DataFrame(satirlar)

    # ------------------------------------------------------------------- JSON
    def sozluk(self) -> dict:
        return asdict(self)

    @classmethod
    def sozlukten(cls, d: dict) -> "HaliParam":
        d = dict(d)

        def dag(x):
            return Dagilim(**{**x, "veri": tuple(x.get("veri", ()))}) if isinstance(x, dict) else x

        for f in fields(cls):
            if f.name in d and isinstance(d[f.name], dict):
                d[f.name] = dag(d[f.name])
        if "urunler" in d:
            d["urunler"] = tuple(Urun(**{**u, "top_uzunlugu": dag(u["top_uzunlugu"])}) for u in d["urunler"])
        if "molalar" in d:
            d["molalar"] = tuple(tuple(m) for m in d["molalar"])
        if "kaynaklar" in d:
            d["kaynaklar"] = tuple(tuple(k) for k in d["kaynaklar"])
        return cls(**d)

    def kaydet(self, yol) -> None:
        Path(yol).write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def yukle(cls, yol) -> "HaliParam":
        return cls.sozlukten(json.loads(Path(yol).read_text(encoding="utf-8")))
