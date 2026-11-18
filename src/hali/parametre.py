"""Halı dokuma salonu parametreleri.

Bütün sayılar tek yerde durur ve her birinin bir `kaynak` etiketi vardır:
"VARSAYIM" (henüz ölçülmedi), "FABRİKA" (fabrikadan gelen sabit bilgi) ya da
"ÖLÇÜM: ..." (iş etüdünden geldi). Ölçüm geldikçe `src.hali.is_etudu`
fonksiyonları ya da JSON dosyası (`data/hali/parametreler.json`) ile değiştirilir.

Birimler: süreler dakika, kopuş ve arıza sıklıkları *dokuma saati* başına,
uzunluklar metre, tarak ve sıra sıklığı 10 cm başına.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

import numpy as np

VARSAYIM = "VARSAYIM"
FABRIKA = "FABRİKA"
ROLLER = ("operator", "telci")


# --------------------------------------------------------------------- dağılım
@dataclass(frozen=True)
class Dagilim:
    """Rastgele süre/uzunluk/hız. tip: sabit | ucgen | ustel | normal | lognormal | ampirik.

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
        """Değeri k katına çıkarır (ör. SMED ile %40 kısalma: k=0.6)."""
        return replace(self, a=self.a * k, b=self.b * k, c=self.c * k, veri=tuple(v * k for v in self.veri))

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


# --------------------------------------------------------------------- tezgâh
@dataclass(frozen=True)
class Tezgah:
    """Bir tezgâhın sabit bilgileri ve değişken devri.

    tarak: 10 cm'deki tarak (çözgü) sıklığı · sira_10cm: 10 cm'deki atkı sırası
    (kalite kartından; bilinmiyorsa VARSAYIM) · devir: dk başına devir dağılımı.
    """
    ad: str
    marka: str
    tarak: int
    en_m: float
    renk: int
    tarak_sayisi: int
    sira_10cm: float
    devir: Dagilim = field(default_factory=lambda: ucgen(70, 85, 100))
    kopus_carpani: float = 1.0
    kaynak: str = FABRIKA          # marka, tarak, en, renk, tarak sayısı
    sira_kaynak: str = VARSAYIM

    def hiz_m_dk(self, devir: float, atki_sistemi: int) -> float:
        """Devirden halı boyuna: m/dk = devir / (sıra/m × sıra başına atkı)."""
        return devir / (self.sira_10cm * 10 * atki_sistemi)


# (ad, marka, tarak/10 cm, en m, renk, tarak sayısı) — fabrikadan, 2026-11-18
_FABRIKA_TEZGAHLARI = (
    ("T01", "Schönherr", 42, 5, 8, 2100),
    ("T02", "Van De Wiele", 42, 4, 7, 1680),
    ("T03", "Van De Wiele", 42, 4, 7, 1716),
    ("T04", "Van De Wiele", 42, 4, 7, 1716),
    ("T05", "Van De Wiele", 42, 4, 7, 1680),
    ("T06", "Schönherr", 50, 4, 6, 2000),
    ("T07", "Schönherr", 50, 4, 8, 2000),
    ("T08", "Schönherr", 50, 4, 8, 2000),
    ("T09", "Van De Wiele-Schönherr", 50, 4, 8, 2000),
    ("T10", "Van De Wiele", 50, 4, 8, 2020),
    ("T11", "Schönherr", 70, 4, 8, 2800),
    ("T12", "Van De Wiele", 50, 4, 8, 2000),
    ("T13", "Van De Wiele", 42, 4, 7, 1680),
    ("T14", "Van De Wiele", 42, 4, 7, 1680),
)


def fabrika_tezgahlari() -> tuple[Tezgah, ...]:
    """Fabrikanın 14 tezgâhı. Sıra sıklığı VARSAYIM: tarak × 1,5 (kalite kartıyla değiştirin).

    Çok renkli ve sık tezgâhlarda kopuş biraz daha sık varsayılır (VARSAYIM).
    """
    return tuple(
        Tezgah(ad, marka, tarak, float(en), renk, ts, sira_10cm=round(tarak * 1.5),
               kopus_carpani=round(1.0 + 0.05 * (renk - 7) + 0.004 * (tarak - 42), 3))
        for ad, marka, tarak, en, renk, ts in _FABRIKA_TEZGAHLARI)


def tezgah_uret(n: int, sablon: Tezgah | None = None) -> tuple[Tezgah, ...]:
    """Panel ve testler için n adet aynı tezgâh (şablon varsayılan: T02 tipi)."""
    s = sablon or fabrika_tezgahlari()[1]
    return tuple(replace(s, ad=f"T{i + 1:02d}") for i in range(n))


# Hangi iş hangi rolün? (sahada farklıysa değiştirin)
VARSAYILAN_ROLLER = (("atki_kopusu", "operator"), ("top_indirme", "operator"), ("ayar", "operator"),
                     ("renk_degisimi", "operator"), ("kontrol", "operator"), ("cozgu_kopusu", "telci"),
                     ("besleme", "telci"))


# ------------------------------------------------------------------- parametre
@dataclass(frozen=True)
class HaliParam:
    # Salon
    tezgahlar: tuple[Tezgah, ...] = field(default_factory=fabrika_tezgahlari)
    yuz_sayisi: int = 2                      # yüz yüze tezgâh aynı anda 2 halı dokur
    atki_sistemi: int = 2                    # bir sırada kaç atkı (2 ya da 3 atkılı)

    # Personel: her tezgâhta bir operatör ve bir telci (fabrika bilgisi)
    operator_basina_tezgah: int = 1
    telci_basina_tezgah: int = 1
    is_rolleri: tuple[tuple[str, str], ...] = VARSAYILAN_ROLLER

    # Siparişler ve değişimler
    top_uzunlugu: Dagilim = field(default_factory=lambda: ucgen(20, 30, 40))   # m
    renk_degisim_olasiligi: float = 0.30     # yeni topta renk/ürün değişimi gerekme olasılığı
    desen_degisim_olasiligi: float = 0.40    # renk değişmeden desen değişimi (kısa ayar)
    renk_ekibi: int = 1                      # renk değişimi ekibi sayısı
    renk_ekip_payi: float = 0.85             # renk değişimlerinin ekipçe yapılan payı ("büyük oranda")
    renk_degisim: Dagilim = field(default_factory=lambda: ucgen(60, 90, 150))
    ayar: Dagilim = field(default_factory=lambda: ucgen(10, 20, 40))           # desen değişimi / ayar

    # Kopuşlar (dokuma saati başına; tezgâhın kopuş çarpanıyla ölçeklenir)
    atki_kopus_saat: float = 1.5
    cozgu_kopus_saat: float = 2.0            # çözgü + hav ipliği
    atki_mudahale: Dagilim = field(default_factory=lambda: ucgen(0.5, 1.0, 2.0))
    cozgu_mudahale: Dagilim = field(default_factory=lambda: ucgen(1.0, 2.5, 5.0))

    # Diğer personel işleri
    top_indirme: Dagilim = field(default_factory=lambda: ucgen(6, 10, 15))
    besleme_aralik: Dagilim = field(default_factory=lambda: ustel(45))         # dokuma dk; tezgâhı durdurmaz
    besleme_sure: Dagilim = field(default_factory=lambda: ucgen(2, 3, 5))
    kontrol_aralik: Dagilim = field(default_factory=lambda: ustel(30))         # halı yüzü kontrolü / hata düzeltme
    kontrol_sure: Dagilim = field(default_factory=lambda: ucgen(2, 4, 8))      # tezgâhı durdurmaz
    yurume_tezgah_arasi: float = 0.15        # dk / tezgâh aralığı
    yurume_sabit: float = 0.10
    secim_kurali: str = "oncelikli"          # fifo | en_yakin | oncelikli (duran tezgâh önce)

    # Arıza ve bakım
    ariza_mtbf_saat: float = 40.0
    ariza_onarim: Dagilim = field(default_factory=lambda: ucgen(20, 45, 120))
    teknisyen_sayisi: int = 2

    # Çözgü
    cozgu_uzunlugu_m: float = 600.0
    cozgu_degisim: Dagilim = field(default_factory=lambda: ucgen(120, 180, 300))
    cozgu_ekibi: int = 1

    # Vardiya, mola, kişisel ihtiyaç
    vardiya_dk: float = 480.0
    molalar: tuple[tuple[float, float], ...] = ((120, 15), (240, 30), (360, 15))
    mola_duzeni: str = "toplu"               # toplu | kademeli | capraz | yedek
    yedek_sayisi: int = 2                    # yedek düzeninde yüzer personel
    mola_dalga_sayisi: int = 4               # yedek düzeninde personel kaç dalgada çıkar
    kisisel_aralik: Dagilim = field(default_factory=lambda: ustel(120))
    kisisel_sure: Dagilim = field(default_factory=lambda: ucgen(3, 5, 10))

    # Koşu
    sure_gun: float = 7.0
    isinma_dk: float = 480.0

    kaynaklar: tuple[tuple[str, str], ...] = (
        ("tezgahlar", FABRIKA), ("operator_basina_tezgah", FABRIKA), ("telci_basina_tezgah", FABRIKA),
        ("renk_ekip_payi", "FABRİKA (\"büyük oranda\"), oran VARSAYIM"))

    # ----------------------------------------------------------- türetilenler
    @property
    def tezgah_sayisi(self) -> int:
        return len(self.tezgahlar)

    def kisi_sayisi(self, rol: str) -> int:
        m = self.operator_basina_tezgah if rol == "operator" else self.telci_basina_tezgah
        return -(-self.tezgah_sayisi // m)

    @property
    def operator_sayisi(self) -> int:
        return self.kisi_sayisi("operator")

    @property
    def personel_sayisi(self) -> int:
        return sum(self.kisi_sayisi(r) for r in ROLLER) + (self.yedek_sayisi if self.mola_duzeni == "yedek" else 0)

    @property
    def vardiya_basina_dk(self) -> float:
        return self.vardiya_dk

    @property
    def bitis_dk(self) -> float:
        return self.isinma_dk + self.sure_gun * 1440

    def rol(self, is_turu: str) -> str:
        return dict(self.is_rolleri)[is_turu]

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

    def tezgah_guncelle(self, ad: str, **degisiklik) -> "HaliParam":
        """Tek bir tezgâhın alanlarını değiştirir (ör. ölçülmüş devir dağılımı)."""
        yeni = tuple(replace(t, **degisiklik) if t.ad == ad else t for t in self.tezgahlar)
        if yeni == self.tezgahlar and ad not in {t.ad for t in self.tezgahlar}:
            raise KeyError(ad)
        return replace(self, tezgahlar=yeni)

    def tablo(self):
        """Parametre, değer ve kaynak tablosu (rapor ve panel için)."""
        import pandas as pd
        satirlar = []
        for f in fields(self):
            if f.name in ("kaynaklar", "tezgahlar"):
                continue
            v = getattr(self, f.name)
            satirlar.append({"Parametre": f.name, "Değer": str(v), "Kaynak": self.kaynak(f.name)})
        return pd.DataFrame(satirlar)

    def tezgah_tablosu(self):
        import pandas as pd
        return pd.DataFrame([{
            "Tezgâh": t.ad, "Marka": t.marka, "Tarak (10 cm)": t.tarak, "En (m)": t.en_m, "Renk": t.renk,
            "Tarak sayısı": t.tarak_sayisi, "Sıra (10 cm)": t.sira_10cm, "Devir (/dk)": str(t.devir),
            "Ort. m²/saat (kesintisiz)": round(t.hiz_m_dk(t.devir.ortalama, self.atki_sistemi) * 60
                                              * t.en_m * self.yuz_sayisi, 1),
            "Kopuş çarpanı": t.kopus_carpani, "Kaynak": t.kaynak,
            "Sıra kaynağı": t.sira_kaynak, "Devir kaynağı": t.devir.kaynak} for t in self.tezgahlar])

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
        if "tezgahlar" in d:
            d["tezgahlar"] = tuple(Tezgah(**{**t, "devir": dag(t["devir"])}) for t in d["tezgahlar"])
        for k in ("molalar", "kaynaklar", "is_rolleri"):
            if k in d:
                d[k] = tuple(tuple(m) for m in d[k])
        return cls(**d)

    def kaydet(self, yol) -> None:
        Path(yol).write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def yukle(cls, yol) -> "HaliParam":
        return cls.sozlukten(json.loads(Path(yol).read_text(encoding="utf-8")))
