"""Halı salonu senaryoları, replikasyon (ortak rastgele sayılar) ve karşılaştırma.

Senaryo i'nin replikasyon j'si her zaman aynı tohumla koşar; böylece farklar
eşleştirilmiş t aralığıyla (src.analiz.eslestirilmis_fark) değerlendirilir.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

import pandas as pd

from src.analiz import bicimle, eslestirilmis_fark, guven_araligi
from src.hali.model import kos
from src.hali.parametre import HaliParam

TABAN_SEED = 7_000


def _olcekle(p: HaliParam, alanlar, k) -> HaliParam:
    return replace(p, **{a: getattr(p, a).olcekle(k) for a in alanlar})


YENI_PERSONEL = (("H03", 0), ("H07", 0), ("H11", 0), ("H14", 0))


SENARYOLAR: dict[str, tuple[str, Callable[[HaliParam], HaliParam]]] = {
    "H0": ("Temel: tezgâh başına 1 halfe + 1 telci, herkes aynı anda molada", lambda p: p),
    "H1": ("Ayrı ayrı mola, komşu aynı rol bakar",
           lambda p: replace(p, mola_zamani="ayri", mola_kapsama="komsu")),
    "H2": ("Ayrı ayrı mola, halfe ve telci birbirine bakar",
           lambda p: replace(p, mola_zamani="ayri", mola_kapsama="capraz")),
    "H3": ("Ayrı ayrı mola, yedek personel bakar (+2 kişi)",
           lambda p: replace(p, mola_zamani="ayri", mola_kapsama="yedek")),
    "H4": ("1 telci / 2 tezgâh", lambda p: replace(p, telci_basina_tezgah=2)),
    "H5": ("1 halfe / 2 tezgâh", lambda p: replace(p, halfe_basina_tezgah=2)),
    "H6": ("1 telci / 2 tezgâh + ayrı mola, birbirine bakar",
           lambda p: replace(p, telci_basina_tezgah=2, mola_zamani="ayri", mola_kapsama="capraz")),
    "H7": ("Renk ekibi 2'ye çıkar", lambda p: replace(p, renk_ekibi=p.renk_ekibi + 1)),
    "H8": ("SMED: renk değişimi %40 kısa", lambda p: _olcekle(p, ("renk_degisim",), 0.6)),
    "H9": ("İplik kalitesi: kopuşlar %30 az",
           lambda p: replace(p, atki_kopus_saat=p.atki_kopus_saat * 0.7, cozgu_kopus_saat=p.cozgu_kopus_saat * 0.7)),
    "H10": ("Önleyici bakım: arıza aralığı ×1,5", lambda p: replace(p, ariza_mtbf_saat=p.ariza_mtbf_saat * 1.5)),
    "H11": ("Devir +%10 (kopuş +%20)",
            lambda p: replace(p, tezgahlar=tuple(replace(t, devir=t.devir.olcekle(1.1)) for t in p.tezgahlar),
                              atki_kopus_saat=p.atki_kopus_saat * 1.2, cozgu_kopus_saat=p.cozgu_kopus_saat * 1.2)),
    "H12": ("Telci, halfenin atkı kopuşu ve kontrolüne yardım eder", lambda p: replace(p, telci_yardim=True)),
    "H13": ("Yorgunluk yok (karşılaştırma için)", lambda p: replace(p, yorgunluk_orani=0.0)),
    "H14": ("Yorgunluk iki kat (saatte %6)", lambda p: replace(p, yorgunluk_orani=p.yorgunluk_orani * 2)),
    "H15": ("4 yeni halfe işe başlar (öğrenme eğrisi)", lambda p: replace(p, deneyim=YENI_PERSONEL)),
}

METRIKLER = {
    "m2_vardiya": ("Salon m²/vardiya", 0),
    "m2_vardiya_tezgah": ("Tezgâh başına m²/vardiya", 1),
    "tezgah_verimi": ("Dokuma oranı", 3),
    "girisim": ("Personel bekleme oranı", 3),
    "halfe_doluluk": ("Halfe doluluğu", 3),
    "ort_yorgunluk": ("Ort. yorgunluk çarpanı", 3),
    "telci_doluluk": ("Telci doluluğu", 3),
    "m2_personel_saat": ("m² / personel-saat", 1),
}


def senaryo_param(kod: str, temel: HaliParam | None = None) -> HaliParam:
    return SENARYOLAR[kod][1](temel or HaliParam())


def _tek(args) -> dict:
    p, seed = args
    return dict(kos(p, seed).ozet, seed=seed)


def replikasyon(p: HaliParam, n: int = 20, taban_seed: int = TABAN_SEED, paralel: bool = False,
                ilerleme: Callable[[float], None] | None = None) -> pd.DataFrame:
    isler = [(p, taban_seed + i) for i in range(n)]
    if paralel:
        from src.deney import _havuz
        return pd.DataFrame(list(_havuz().map(_tek, isler)))
    satirlar = []
    for k, is_ in enumerate(isler):
        satirlar.append(_tek(is_))
        if ilerleme:
            ilerleme((k + 1) / n)
    return pd.DataFrame(satirlar)


def senaryolari_kos(kodlar=tuple(SENARYOLAR), n: int = 20, temel: HaliParam | None = None,
                    paralel: bool = True, taban_seed: int = TABAN_SEED) -> dict[str, pd.DataFrame]:
    return {k: replikasyon(senaryo_param(k, temel), n, taban_seed, paralel) for k in kodlar}


def karsilastir(sonuclar: dict[str, pd.DataFrame], referans: str = "H0") -> pd.DataFrame:
    """Ortalama ± %95 YG ve referansa göre eşleştirilmiş farklar."""
    ref = sonuclar[referans]
    satirlar = []
    for kod, df in sonuclar.items():
        s = {"Senaryo": kod, "Açıklama": SENARYOLAR.get(kod, (kod,))[0],
             "Personel": int(df["personel_sayisi"].iloc[0])}
        for m, (etiket, b) in METRIKLER.items():
            s[etiket] = bicimle(*guven_araligi(df[m]), b)
        if kod != referans:
            f = eslestirilmis_fark(ref["m2_vardiya"], df["m2_vardiya"])
            s["Δ m²/vardiya"] = f"{f['fark']:+.0f} [{f['alt']:+.0f}, {f['ust']:+.0f}]" + ("" if f["anlamli"] else " (anlamsız)")
            s["Δ %"] = f"{100 * f['fark'] / ref['m2_vardiya'].mean():+.1f}"
        else:
            s["Δ m²/vardiya"], s["Δ %"] = "-", "-"
        satirlar.append(s)
    return pd.DataFrame(satirlar)


def durum_ozeti(sonuclar: dict[str, pd.DataFrame], onek: str) -> pd.DataFrame:
    """Senaryo × durum oran tablosu (onek: 'tz:' tezgâh, 'hf:' halfe)."""
    return pd.DataFrame({k: {c[len(onek):]: df[c].mean() for c in df.columns if c.startswith(onek)}
                         for k, df in sonuclar.items()}).T


def atama_egrisi(rol: str = "telci", tezgah_sayilari=(1, 2, 3, 4), n: int = 10, temel: HaliParam | None = None,
                 katki_tl_m2: float = 60.0, personel_tl_saat: float = 250.0,
                 paralel: bool = True, taban_seed: int = TABAN_SEED) -> pd.DataFrame:
    """Kişi başına tezgâh sayısına göre üretim, girişim ve vardiya başına net katkı.

    rol: "halfe" ya da "telci". katki_tl_m2 ve personel_tl_saat VARSAYIM'dır.
    Net katkı/vardiya = m²/vardiya × katkı payı − personel sayısı × vardiya saati × saat maliyeti.
    """
    temel = temel or HaliParam()
    alan = "halfe_basina_tezgah" if rol == "halfe" else "telci_basina_tezgah"
    satirlar = []
    for m in tezgah_sayilari:
        p = replace(temel, **{alan: m})
        df = replikasyon(p, n, taban_seed, paralel)
        net = df["m2_vardiya"] * katki_tl_m2 - df["personel_sayisi"] * p.vardiya_dk / 60 * personel_tl_saat
        s = {"tezgah_kisi": m, "kisi_sayisi": p.kisi_sayisi(rol), "personel_sayisi": p.personel_sayisi}
        for c in ("m2_vardiya", "tezgah_verimi", "girisim", f"{rol}_doluluk", "m2_personel_saat"):
            s[c], s[c + "_yg"] = guven_araligi(df[c])
        s["net_katki_vardiya"], s["net_katki_vardiya_yg"] = guven_araligi(net)
        satirlar.append(s)
    return pd.DataFrame(satirlar)
