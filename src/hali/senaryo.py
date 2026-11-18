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


SENARYOLAR: dict[str, tuple[str, Callable[[HaliParam], HaliParam]]] = {
    "H0": ("Temel: 4 tezgâh/operatör, toplu mola", lambda p: p),
    "H1": ("3 tezgâh/operatör (daha çok operatör)", lambda p: replace(p, operator_basina_tezgah=3)),
    "H2": ("6 tezgâh/operatör (daha az operatör)", lambda p: replace(p, operator_basina_tezgah=6)),
    "H3": ("Kademeli mola, komşu operatör bakar", lambda p: replace(p, mola_duzeni="kademeli")),
    "H4": ("Yedek operatörle sırayla mola", lambda p: replace(p, mola_duzeni="yedek")),
    "H5": ("İplik kalitesi: kopuşlar %30 az",
           lambda p: replace(p, atki_kopus_saat=p.atki_kopus_saat * 0.7, cozgu_kopus_saat=p.cozgu_kopus_saat * 0.7)),
    "H6": ("SMED: ayar ve çözgü değişimi %40 kısa", lambda p: _olcekle(p, ("ayar", "cozgu_degisim"), 0.6)),
    "H7": ("Önleyici bakım: arıza aralığı ×1,5", lambda p: replace(p, ariza_mtbf_saat=p.ariza_mtbf_saat * 1.5)),
    "H8": ("Öncelik kuralı: duran tezgâh önce", lambda p: replace(p, secim_kurali="oncelikli")),
    "H9": ("Yerleşim: yürüme süresi %50 kısa",
           lambda p: replace(p, yurume_tezgah_arasi=p.yurume_tezgah_arasi / 2, yurume_sabit=p.yurume_sabit / 2)),
    "H10": ("Tezgâh hızı +%10 (kopuş +%20)",
            lambda p: replace(p, devir=p.devir * 1.1, atki_kopus_saat=p.atki_kopus_saat * 1.2,
                              cozgu_kopus_saat=p.cozgu_kopus_saat * 1.2)),
}

METRIKLER = {
    "m2_gun": ("Üretim (m²/gün)", 0),
    "tezgah_verimi": ("Tezgâh dokuma oranı", 3),
    "girisim": ("Operatör bekleme oranı", 3),
    "operator_doluluk": ("Operatör doluluğu", 3),
    "m2_operator_saat": ("m² / operatör-saat", 1),
    "ort_bekleme_dk": ("Ort. müdahale bekleme (dk)", 2),
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
             "Operatör": int(df["operator_sayisi"].iloc[0])}
        for m, (etiket, b) in METRIKLER.items():
            s[etiket] = bicimle(*guven_araligi(df[m]), b)
        if kod != referans:
            f = eslestirilmis_fark(ref["m2_gun"], df["m2_gun"])
            s["Δ m²/gün"] = f"{f['fark']:+.0f} [{f['alt']:+.0f}, {f['ust']:+.0f}]" + ("" if f["anlamli"] else " (anlamsız)")
            s["Δ %"] = f"{100 * f['fark'] / ref['m2_gun'].mean():+.1f}"
        else:
            s["Δ m²/gün"], s["Δ %"] = "-", "-"
        satirlar.append(s)
    return pd.DataFrame(satirlar)


def durum_ozeti(sonuclar: dict[str, pd.DataFrame], onek: str) -> pd.DataFrame:
    """Senaryo × durum oran tablosu (onek: 'tz:' tezgâh, 'op:' operatör)."""
    return pd.DataFrame({k: {c[len(onek):]: df[c].mean() for c in df.columns if c.startswith(onek)}
                         for k, df in sonuclar.items()}).T


def atama_egrisi(tezgah_sayilari=(2, 3, 4, 5, 6, 8), n: int = 10, temel: HaliParam | None = None,
                 katki_tl_m2: float = 60.0, operator_tl_saat: float = 250.0,
                 paralel: bool = True, taban_seed: int = TABAN_SEED) -> pd.DataFrame:
    """Operatör başına tezgâh sayısına göre üretim, girişim ve günlük net katkı.

    katki_tl_m2 ve operator_tl_saat VARSAYIM'dır (fabrika verisiyle değiştirin).
    Net katkı = m²/gün × katkı payı − operatör sayısı × 24 saat × saat maliyeti.
    """
    temel = temel or HaliParam()
    satirlar = []
    for m in tezgah_sayilari:
        p = replace(temel, operator_basina_tezgah=m)
        df = replikasyon(p, n, taban_seed, paralel)
        net = df["m2_gun"] * katki_tl_m2 - df["operator_sayisi"] * 24 * operator_tl_saat
        s = {"tezgah_operator": m, "operator_sayisi": p.operator_sayisi}
        for c in ("m2_gun", "tezgah_verimi", "girisim", "operator_doluluk", "m2_operator_saat"):
            s[c], s[c + "_yg"] = guven_araligi(df[c])
        s["net_katki_gun"], s["net_katki_gun_yg"] = guven_araligi(net)
        satirlar.append(s)
    return pd.DataFrame(satirlar)
