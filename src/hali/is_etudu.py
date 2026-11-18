"""İş etüdü ile simülasyon arasındaki köprü.

1. Zaman etüdü  -> gözlenen süre, performans puanı -> normal süre, standart süre,
                   gerekli gözlem sayısı ve modele girecek dağılım.
2. İş örneklemesi -> durum oranları, güven aralıkları, gerekli gözlem sayısı.
3. Kopuş / arıza kayıtları -> dokuma saati başına kopuş sıklığı, MTBF, onarım süresi.
4. Sanal iş örneklemesi -> etüde başlamadan önce simülasyon üzerinde "kaç tur gözlem
   yeterli?" sorusunu deneme; ölçüm gelince model ile sahayı karşılaştırma (doğrulama).

Önemli: Modelde mola ve kişisel ihtiyaç ayrı olaylar olarak yer alır. Bu yüzden
modele *normal süre* (performans puanıyla düzeltilmiş) verilir; tolerans payları
eklenmiş standart süre verilirse kayıplar iki kez sayılır.

Form şablonları: data/hali/is_etudu/*.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.hali.model import OPERATOR_DURUMLARI, TEZGAH_DURUMLARI, HaliSonuc
from src.hali.parametre import Dagilim, HaliParam, sabit, ucgen

# Zaman etüdü formundaki model_alani sütununun alabileceği değerler
SURE_ALANLARI = ("atki_mudahale", "cozgu_mudahale", "top_indirme", "ayar", "besleme_sure",
                 "cozgu_degisim", "ariza_onarim", "kisisel_sure")


def _z(guven: float) -> float:
    return float(stats.norm.ppf(0.5 + guven / 2))


# ---------------------------------------------------------------- zaman etüdü
def gerekli_gozlem_zaman(sureler, guven: float = 0.95, hata: float = 0.05) -> int:
    """Ortalamayı ±hata (göreli) içinde tahmin etmek için gereken döngü sayısı.

    n' = (z·s / (hata·x̄))². guven=0.95, hata=0.05 için klasik 40·√(nΣx²−(Σx)²)/Σx
    formülüne denktir (z≈2 yaklaşımıyla).
    """
    x = np.asarray(sureler, float)
    if x.size < 2:
        return 0
    return int(np.ceil((_z(guven) * x.std(ddof=1) / (hata * x.mean())) ** 2))


def standart_sure(sureler, performans=100.0, tolerans: float = 0.15) -> dict:
    """Gözlenen süreler (dk) ve performans puanı (%, tek değer ya da gözlem başına)."""
    x = np.asarray(sureler, float)
    perf = np.broadcast_to(np.asarray(performans, float), x.shape)
    normal = x * perf / 100
    return {"n": int(x.size), "gozlenen_ort": float(x.mean()), "gozlenen_ss": float(x.std(ddof=1)) if x.size > 1 else 0.0,
            "performans_ort": float(perf.mean()), "normal_sure": float(normal.mean()),
            "tolerans": tolerans, "standart_sure": float(normal.mean() * (1 + tolerans)),
            "gerekli_n": gerekli_gozlem_zaman(x)}


def dagilim_oner(normal_sureler, kaynak: str = "ÖLÇÜM") -> Dagilim:
    """Normal sürelerden model dağılımı.

    30 ve üzeri gözlemde üçgen / normal / lognormal arasından KS istatistiği en
    küçük olan seçilir; daha az gözlemde %5-medyan-%95 üçgen yaklaşımı kullanılır.
    """
    x = np.asarray(normal_sureler, float)
    if x.size and np.ptp(x) == 0:
        return sabit(float(x[0]), kaynak=kaynak)
    if x.size < 30:
        a, m, c = np.percentile(x, [5, 50, 95]) if x.size >= 3 else (x.min(), x.mean(), x.max())
        return ucgen(float(a), float(min(max(m, a), c)), float(c), kaynak=kaynak)
    from src.kalibrasyon import dagilim_uydur
    tablo = dagilim_uydur(x, adaylar=("ucgen", "normal", "lognormal"))
    en = tablo.iloc[0]
    if en["dagilim"] == "ucgen":
        c, loc, scale = en["parametreler"]
        return ucgen(loc, loc + c * scale, loc + scale, kaynak=kaynak)
    return Dagilim(en["dagilim"], float(x.mean()), float(x.std(ddof=1)), kaynak=kaynak)


def zaman_etudu_analiz(df: pd.DataFrame, toleranslar: dict | None = None) -> pd.DataFrame:
    """Zaman etüdü formu -> eleman bazında standart süre tablosu.

    Sütunlar: eleman, model_alani, sure_dk, performans (%; yoksa 100).
    """
    toleranslar = toleranslar or {}
    satirlar = []
    for (eleman, alan), g in df.groupby(["eleman", "model_alani"], sort=False):
        perf = g["performans"] if "performans" in g else 100.0
        s = standart_sure(g["sure_dk"], perf, toleranslar.get(eleman, 0.15))
        s["yeterli"] = s["n"] >= s["gerekli_n"]
        dag = dagilim_oner(g["sure_dk"].to_numpy() * np.asarray(perf, float) / 100, f"ÖLÇÜM: zaman etüdü n={s['n']}")
        satirlar.append({"eleman": eleman, "model_alani": alan, **s, "dagilim": dag})
    return pd.DataFrame(satirlar)


# ------------------------------------------------------------- iş örneklemesi
def gerekli_gozlem_ornekleme(p: float, hata: float = 0.03, guven: float = 0.95, goreli: bool = False) -> int:
    """n = z²·p(1−p)/e². goreli=True ise e = hata·p (ör. ±%5 göreli)."""
    if p <= 0 or p >= 1:
        return 0
    e = hata * p if goreli else hata
    return int(np.ceil(_z(guven) ** 2 * p * (1 - p) / e ** 2))


def is_ornekleme_analiz(df: pd.DataFrame, guven: float = 0.95, hata: float = 0.03) -> pd.DataFrame:
    """İş örneklemesi formu -> kaynak tipi × durum oranı, %95 YG ve gerekli gözlem.

    Sütunlar: kaynak_tipi (operator | tezgah), kaynak, durum (model durum kodları).
    """
    z = _z(guven)
    satirlar = []
    for tip, g in df.groupby("kaynak_tipi"):
        n = len(g)
        sayim = g["durum"].value_counts()
        durumlar = OPERATOR_DURUMLARI if tip == "operator" else TEZGAH_DURUMLARI
        for d in dict.fromkeys(list(durumlar) + list(sayim.index)):
            k = int(sayim.get(d, 0))
            p = k / n
            yg = z * np.sqrt(p * (1 - p) / n)
            satirlar.append({"kaynak_tipi": tip, "durum": d, "gozlem": k, "toplam": n, "oran": p,
                             "alt": max(0.0, p - yg), "ust": min(1.0, p + yg),
                             "gerekli_n": gerekli_gozlem_ornekleme(p, hata, guven)})
    return pd.DataFrame(satirlar)


def sanal_is_ornekleme(sonuc: HaliSonuc, tur_sayisi: int, seed: int = 0) -> pd.DataFrame:
    """Simülasyon üzerinde iş örneklemesi: rastgele anlarda tüm kaynakları gözler.

    Çıktı, sahadaki iş örneklemesi formuyla aynı biçimdedir.
    """
    rng = np.random.default_rng(seed)
    c = sonuc.cizelge
    t0, t1 = c["bas"].min(), c["bit"].max()
    anlar = np.sort(rng.uniform(t0, t1, tur_sayisi))
    satirlar = []
    for kaynak, g in c.groupby("kaynak", sort=False):
        g = g.sort_values("bas")
        idx = np.clip(np.searchsorted(g["bit"].to_numpy(), anlar, side="right"), 0, len(g) - 1)
        tip = "tezgah" if kaynak.startswith("T") else "operator"
        for tur, (an, d) in enumerate(zip(anlar, g["durum"].to_numpy()[idx])):
            satirlar.append((tur + 1, round(float(an), 2), tip, kaynak, d))
    return pd.DataFrame(satirlar, columns=["tur", "zaman_dk", "kaynak_tipi", "kaynak", "durum"])


def gercek_oranlar(sonuc: HaliSonuc) -> pd.DataFrame:
    """Simülasyondaki zaman ağırlıklı gerçek durum oranları (iş örneklemesinin hedefi)."""
    satir = [("operator", d, float(sonuc.operator[d].mean())) for d in OPERATOR_DURUMLARI]
    satir += [("tezgah", d, float(sonuc.tezgah[d].mean())) for d in TEZGAH_DURUMLARI]
    return pd.DataFrame(satir, columns=["kaynak_tipi", "durum", "gercek"])


def karsilastir(gozlem: pd.DataFrame, model_oranlari: pd.DataFrame) -> pd.DataFrame:
    """İş örneklemesi tahmini ile model oranlarını yan yana koyar.

    Sahadaki gözlemlerle kullanıldığında model doğrulamasıdır: model oranı
    örneklemenin güven aralığı içinde mi?
    """
    analiz = is_ornekleme_analiz(gozlem)
    m = analiz.merge(model_oranlari, on=["kaynak_tipi", "durum"], how="outer").fillna(0)
    m["aralikta"] = (m["gercek"] >= m["alt"]) & (m["gercek"] <= m["ust"])
    return m


def yakinsama(sonuc: HaliSonuc, turlar=(10, 25, 50, 100, 200, 400), tekrar: int = 50, seed: int = 0) -> pd.DataFrame:
    """Tur sayısına göre iş örneklemesi hatası (ortalama mutlak sapma, puan)."""
    gercek = gercek_oranlar(sonuc)
    satirlar = []
    for n in turlar:
        hatalar = {"operator": [], "tezgah": []}
        for r in range(tekrar):
            g = sanal_is_ornekleme(sonuc, n, seed * 10_000 + n * 100 + r)
            a = is_ornekleme_analiz(g).merge(gercek, on=["kaynak_tipi", "durum"])
            for tip in hatalar:
                x = a[a["kaynak_tipi"] == tip]
                hatalar[tip].append(float((x["oran"] - x["gercek"]).abs().max()))
        satirlar.append({"tur": n, "operator_gozlem": n * len(sonuc.operator),
                         "operator_maks_hata": float(np.mean(hatalar["operator"])),
                         "tezgah_maks_hata": float(np.mean(hatalar["tezgah"]))})
    return pd.DataFrame(satirlar)


# -------------------------------------------------------- kopuş ve arıza kayıtları
def kopus_analiz(df: pd.DataFrame, dokuma_saati: float) -> pd.DataFrame:
    """Kopuş kayıtları -> tür başına sıklık (/dokuma saati), bekleme ve müdahale süreleri.

    Sütunlar: tezgah, tur (atki | cozgu), durus_dk, mudahale_bas_dk, bitis_dk
    (aynı başlangıca göre dakika). dokuma_saati: gözlem süresince toplam dokuma
    saati (tezgâh sayısı × gözlem saati × dokuma oranı).
    """
    satirlar = []
    for tur, g in df.groupby("tur"):
        bek = g["mudahale_bas_dk"] - g["durus_dk"]
        mud = g["bitis_dk"] - g["mudahale_bas_dk"]
        satirlar.append({"tur": tur, "adet": len(g), "saat_basina": len(g) / dokuma_saati,
                         "ort_bekleme_dk": float(bek.mean()), "ort_mudahale_dk": float(mud.mean()),
                         "mudahale_dagilim": dagilim_oner(mud.to_numpy(), f"ÖLÇÜM: kopuş kaydı n={len(g)}")})
    return pd.DataFrame(satirlar)


def ariza_analiz(df: pd.DataFrame, dokuma_saati: float) -> dict:
    """Arıza kayıtları (tezgah, ariza_bas_dk, onarim_bitis_dk) -> MTBF (dokuma saati), onarım dağılımı."""
    onarim = (df["onarim_bitis_dk"] - df["ariza_bas_dk"]).to_numpy()
    return {"adet": len(df), "mtbf_saat": dokuma_saati / len(df) if len(df) else float("inf"),
            "ort_onarim_dk": float(onarim.mean()),
            "onarim_dagilim": dagilim_oner(onarim, f"ÖLÇÜM: arıza kaydı n={len(df)}")}


# ---------------------------------------------------------- parametre güncelleme
def parametreleri_guncelle(p: HaliParam, zaman: pd.DataFrame | None = None,
                           kopus: pd.DataFrame | None = None, ariza: dict | None = None) -> HaliParam:
    """Analiz tablolarındaki ölçümleri parametrelere yazar ve kaynağını işaretler."""
    if zaman is not None:
        for _, s in zaman.iterrows():
            if s["model_alani"] in SURE_ALANLARI:
                p = p.olcum_ile(s["model_alani"], s["dagilim"], f"zaman etüdü, {s['eleman']}, n={s['n']}")
    if kopus is not None:
        for _, s in kopus.iterrows():
            alan = "atki" if s["tur"] == "atki" else "cozgu"
            p = p.olcum_ile(f"{alan}_kopus_saat", float(s["saat_basina"]), f"kopuş kaydı n={s['adet']}")
            p = p.olcum_ile(f"{alan}_mudahale", s["mudahale_dagilim"], f"kopuş kaydı n={s['adet']}")
    if ariza is not None:
        p = p.olcum_ile("ariza_mtbf_saat", ariza["mtbf_saat"], f"arıza kaydı n={ariza['adet']}")
        p = p.olcum_ile("ariza_onarim", ariza["onarim_dagilim"], f"arıza kaydı n={ariza['adet']}")
    return p
