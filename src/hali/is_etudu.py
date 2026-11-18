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

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.hali.model import PERSONEL_DURUMLARI, TEZGAH_DURUMLARI, HaliSonuc
from src.hali.parametre import Dagilim, HaliParam, sabit, ucgen

# Zaman etüdü formundaki model_alani sütununun alabileceği değerler
SURE_ALANLARI = ("atki_mudahale", "cozgu_mudahale", "top_indirme", "ayar", "renk_degisim", "besleme_sure",
                 "kontrol_sure", "cozgu_degisim", "ariza_onarim", "kisisel_sure")
KAYNAK_TIPLERI = ("tezgah", "operator", "telci", "yedek")


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

    Sütunlar: kaynak_tipi (tezgah | operator | telci), kaynak, durum (model durum kodları),
    isteğe bağlı tarih + tur.

    Bir turdaki gözlemler aynı ana aittir ve birbirine bağlıdır (ör. toplu molada
    herkes aynı anda molada). Tur bilgisi varsa güven aralığı tur ortalamalarından
    (küme örneklemesi) hesaplanır ve gerekli_tur sütunu verilir; yoksa her gözlem
    bağımsız sayılır (binom aralığı), bu da aralığı olduğundan dar gösterebilir.
    """
    z = _z(guven)
    df = df.copy()
    kume = "tur" in df.columns
    if kume:
        df["_tur"] = df["tarih"].astype(str) + "/" + df["tur"].astype(str) if "tarih" in df else df["tur"].astype(str)
    satirlar = []
    for tip, g in df.groupby("kaynak_tipi"):
        n = len(g)
        sayim = g["durum"].value_counts()
        durumlar = TEZGAH_DURUMLARI if tip == "tezgah" else PERSONEL_DURUMLARI
        if kume:
            tur_toplam = g.groupby("_tur").size()
            T = len(tur_toplam)
        for d in dict.fromkeys(list(durumlar) + list(sayim.index)):
            k = int(sayim.get(d, 0))
            p = k / n
            satir = {"kaynak_tipi": tip, "durum": d, "gozlem": k, "toplam": n, "oran": p}
            if kume and T > 1:
                oranlar = (g["durum"].eq(d).groupby(g["_tur"]).sum() / tur_toplam).to_numpy()
                sd = float(oranlar.std(ddof=1))
                yg = float(stats.t.ppf(0.5 + guven / 2, T - 1)) * sd / np.sqrt(T)
                satir["tur_sayisi"] = T
                satir["gerekli_tur"] = int(np.ceil((z * sd / hata) ** 2)) if sd > 0 else 0
            else:
                yg = z * np.sqrt(p * (1 - p) / n)
            satir.update({"alt": max(0.0, p - yg), "ust": min(1.0, p + yg),
                          "gerekli_n": gerekli_gozlem_ornekleme(p, hata, guven)})
            satirlar.append(satir)
    return pd.DataFrame(satirlar)


def sanal_is_ornekleme(sonuc: HaliSonuc, tur_sayisi: int, seed: int = 0) -> pd.DataFrame:
    """Simülasyon üzerinde iş örneklemesi: rastgele anlarda tüm kaynakları gözler.

    Çıktı, sahadaki iş örneklemesi formuyla aynı biçimdedir.
    """
    rng = np.random.default_rng(seed)
    c = sonuc.cizelge
    t0, t1 = c["bas"].min(), c["bit"].max()
    anlar = np.sort(rng.uniform(t0, t1, tur_sayisi))
    tipler = {**{t: "tezgah" for t in sonuc.tezgah["tezgah"]},
              **dict(zip(sonuc.personel["personel"], sonuc.personel["rol"]))}
    satirlar = []
    for kaynak, g in c.groupby("kaynak", sort=False):
        g = g.sort_values("bas")
        idx = np.clip(np.searchsorted(g["bit"].to_numpy(), anlar, side="right"), 0, len(g) - 1)
        tip = tipler[kaynak]
        for tur, (an, d) in enumerate(zip(anlar, g["durum"].to_numpy()[idx])):
            satirlar.append((tur + 1, round(float(an), 2), tip, kaynak, d))
    return pd.DataFrame(satirlar, columns=["tur", "zaman_dk", "kaynak_tipi", "kaynak", "durum"])


def gercek_oranlar(sonuc: HaliSonuc) -> pd.DataFrame:
    """Simülasyondaki zaman ağırlıklı gerçek durum oranları (iş örneklemesinin hedefi)."""
    satir = [(rol, d, float(g[d].mean())) for rol, g in sonuc.personel.groupby("rol") for d in PERSONEL_DURUMLARI]
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
    """Tur sayısına göre iş örneklemesi hatası: kaynak tipi başına en büyük oran sapması (puan)."""
    gercek = gercek_oranlar(sonuc)
    tipler = sorted(set(gercek["kaynak_tipi"]) - {"yedek"})
    satirlar = []
    for n in turlar:
        hatalar = {t: [] for t in tipler}
        for r in range(tekrar):
            g = sanal_is_ornekleme(sonuc, n, seed * 10_000 + n * 100 + r)
            a = is_ornekleme_analiz(g).merge(gercek, on=["kaynak_tipi", "durum"])
            for tip in tipler:
                x = a[a["kaynak_tipi"] == tip]
                hatalar[tip].append(float((x["oran"] - x["gercek"]).abs().max()))
        satir = {"tur": n, "gozlem_tur_basina": int(len(sonuc.tezgah) + len(sonuc.personel))}
        satir.update({f"{t}_maks_hata": float(np.mean(h)) for t, h in hatalar.items()})
        satirlar.append(satir)
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


def devir_analiz(df: pd.DataFrame) -> pd.DataFrame:
    """Devir okumaları (tezgah, devir[, urun]) -> tezgâh başına devir dağılımı."""
    satirlar = []
    for tz, g in df.groupby("tezgah"):
        x = g["devir"].to_numpy(float)
        satirlar.append({"tezgah": tz, "n": len(x), "ort": float(x.mean()), "ss": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
                         "min": float(x.min()), "maks": float(x.max()),
                         "dagilim": dagilim_oner(x, f"ÖLÇÜM: devir okuması n={len(x)}")})
    return pd.DataFrame(satirlar)


def renk_analiz(df: pd.DataFrame) -> dict:
    """Renk değişimi kayıtları -> süre dağılımı (duruştan bitişe), ekip payı, ekibi bekleme."""
    sure = (df["bitis_dk"] - df["durus_dk"]).to_numpy(float)
    ekip = df["yapan"].str.lower().eq("ekip")
    bekleme = (df["ekip_gelis_dk"] - df["durus_dk"])[ekip]
    return {"adet": len(df), "ort_sure_dk": float(sure.mean()), "ekip_payi": float(ekip.mean()),
            "ort_ekip_bekleme_dk": float(bekleme.mean()) if len(bekleme) else 0.0,
            "sure_dagilim": dagilim_oner(sure, f"ÖLÇÜM: renk değişimi kaydı n={len(df)}")}


def uretim_dogrulama(saha: pd.DataFrame, model_tezgah: pd.DataFrame) -> pd.DataFrame:
    """Sahadaki m²/vardiya (tezgah, m2 satırları) ile modelin tezgâh başına m²/vardiya'sı.

    model_tezgah: replikasyonlarda tezgâh tablolarının birleşimi (tezgah, m2_vardiya).
    """
    s = saha.groupby("tezgah")["m2"].agg(saha_ort="mean", saha_n="count", saha_ss="std").reset_index()
    m = model_tezgah.groupby("tezgah")["m2_vardiya"].agg(model_ort="mean").reset_index()
    t = s.merge(m, on="tezgah", how="outer")
    t["fark_%"] = 100 * (t["model_ort"] - t["saha_ort"]) / t["saha_ort"]
    return t


# ---------------------------------------------------------- parametre güncelleme
def parametreleri_guncelle(p: HaliParam, zaman: pd.DataFrame | None = None,
                           kopus: pd.DataFrame | None = None, ariza: dict | None = None,
                           devir: pd.DataFrame | None = None, renk: dict | None = None) -> HaliParam:
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
    if devir is not None:
        adlar = {t.ad for t in p.tezgahlar}
        for _, s in devir.iterrows():
            if s["tezgah"] in adlar:
                p = p.tezgah_guncelle(s["tezgah"], devir=s["dagilim"])
    if renk is not None:
        p = p.olcum_ile("renk_degisim", renk["sure_dagilim"], f"renk değişimi kaydı n={renk['adet']}")
        p = p.olcum_ile("renk_ekip_payi", renk["ekip_payi"], f"renk değişimi kaydı n={renk['adet']}")
    return p


# ----------------------------------------------------------------- tur planı
def tur_plani(baslangic: str, gun: int, tur_vardiya: int, vardiya_baslari=("08:00", "16:00", "00:00"),
              vardiya_dk: float = 480, tur_suresi_dk: float = 8, seed: int = 0) -> pd.DataFrame:
    """Rastgele iş örneklemesi tur saatleri: her vardiyada tur_vardiya tur, çakışmasız."""
    rng = np.random.default_rng(seed)
    satirlar = []
    gun0 = pd.Timestamp(baslangic)
    for g in range(gun):
        for v, bas in enumerate(vardiya_baslari, start=1):
            t0 = gun0 + pd.Timedelta(days=g) + pd.Timedelta(bas + ":00")
            if bas < vardiya_baslari[0]:             # gece vardiyası ertesi güne düşer
                t0 += pd.Timedelta(days=1)
            # çakışmayı önlemek için vardiya, tur sayısı kadar dilime bölünür; her dilimde bir rastgele an
            dilim = vardiya_dk / tur_vardiya
            for k in range(tur_vardiya):
                an = k * dilim + rng.uniform(0, max(0.0, dilim - tur_suresi_dk))
                t = t0 + pd.Timedelta(minutes=float(an))
                satirlar.append({"tarih": t.strftime("%Y-%m-%d"), "vardiya": v, "tur": k + 1,
                                 "saat": t.strftime("%H:%M"), "vardiya_ici_dk": round(an, 1)})
    return pd.DataFrame(satirlar)


# -------------------------------------------------------------- form okuma ve CLI
FORM_KLASORU = Path(__file__).resolve().parents[2] / "data" / "hali" / "is_etudu"
CIKTI = Path(__file__).resolve().parents[2] / "results" / "hali"


def form_oku(yol) -> pd.DataFrame | None:
    """Formu okur, ORNEK satırlarını atar; dosya yoksa ya da veri yoksa None."""
    yol = Path(yol)
    if not yol.exists():
        return None
    df = pd.read_csv(yol)
    ornek = pd.Series(False, index=df.index)
    for c in ("gozlemci", "not"):
        if c in df:
            ornek |= df[c].astype(str).str.contains("ORNEK", na=False)
    df = df[~ornek]
    return df if len(df) else None


def _md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def analiz_et(klasor=FORM_KLASORU, p: HaliParam | None = None, kayit_saat: float | None = None,
              dokuma_orani: float | None = None, n_model: int = 5) -> tuple[HaliParam, str]:
    """Klasördeki bütün formları analiz eder; güncellenmiş parametreler ve Markdown rapor döner.

    kayit_saat: kopuş/arıza kayıtlarının tutulduğu süre (saat, tezgâh başına).
    dokuma_orani: verilmezse iş örneklemesindeki tezgâh 'dokuma' oranı, o da yoksa 0,70.
    """
    from src.hali.senaryo import replikasyon
    klasor = Path(klasor)
    p = p or HaliParam()
    b = ["# İş etüdü analizi", ""]
    zaman = form_oku(klasor / "zaman_etudu.csv")
    ornek = form_oku(klasor / "is_ornekleme.csv")
    kopus = form_oku(klasor / "kopus_kayitlari.csv")
    ariza = form_oku(klasor / "ariza_kayitlari.csv")
    renk = form_oku(klasor / "renk_degisimi_kayitlari.csv")
    devir = form_oku(klasor / "devir_kayitlari.csv")
    uretim = form_oku(klasor / "uretim_kayitlari.csv")

    zt = kt = at = dt = rt = None
    if zaman is not None:
        zt = zaman_etudu_analiz(zaman)
        b += ["## Zaman etüdü", "", _md(zt.assign(dagilim=zt["dagilim"].astype(str)).round(3)), ""]
    if ornek is not None:
        oa = is_ornekleme_analiz(ornek)
        b += ["## İş örneklemesi (saha)", "", _md(oa[oa["gozlem"] > 0].round(3)), ""]
        if dokuma_orani is None:
            x = oa[(oa["kaynak_tipi"] == "tezgah") & (oa["durum"] == "dokuma")]
            dokuma_orani = float(x["oran"].iloc[0]) if len(x) else None
    dokuma_orani = dokuma_orani or 0.70
    if (kopus is not None or ariza is not None) and not kayit_saat:
        b += ["> Kopuş/arıza kaydı var ama `--kayit-saat` verilmedi; sıklıklar hesaplanmadı.", ""]
    elif kayit_saat:
        dokuma_saati = p.tezgah_sayisi * kayit_saat * dokuma_orani
        b += [f"Dokuma saati = {p.tezgah_sayisi} tezgâh × {kayit_saat:g} saat × {dokuma_orani:.2f} = "
              f"{dokuma_saati:.0f} saat", ""]
        if kopus is not None:
            kt = kopus_analiz(kopus, dokuma_saati)
            b += ["## Kopuşlar", "", _md(kt.assign(mudahale_dagilim=kt["mudahale_dagilim"].astype(str)).round(3)), ""]
        if ariza is not None:
            at = ariza_analiz(ariza, dokuma_saati)
            b += ["## Arızalar", "", f"{at['adet']} arıza, MTBF {at['mtbf_saat']:.1f} dokuma saati, "
                  f"ortalama onarım {at['ort_onarim_dk']:.1f} dk ({at['onarim_dagilim']})", ""]
    if renk is not None:
        rt = renk_analiz(renk)
        b += ["## Renk değişimi", "", f"{rt['adet']} değişim, ortalama {rt['ort_sure_dk']:.1f} dk, ekip payı "
              f"%{100 * rt['ekip_payi']:.0f}, ekibi bekleme {rt['ort_ekip_bekleme_dk']:.1f} dk", ""]
    if devir is not None:
        dt = devir_analiz(devir)
        b += ["## Devir", "", _md(dt.assign(dagilim=dt["dagilim"].astype(str)).round(2)), ""]

    p = parametreleri_guncelle(p, zaman=zt, kopus=kt, ariza=at, devir=dt, renk=rt)
    if ornek is not None or uretim is not None:
        reps = [kos_tek(p, 7_000 + i) for i in range(n_model)]
        if ornek is not None:
            model = pd.concat([gercek_oranlar(r) for r in reps]).groupby(["kaynak_tipi", "durum"], as_index=False).mean()
            k = karsilastir(ornek, model)
            k = k[(k["toplam"] > 0) & ((k["oran"] > 0) | (k["gercek"] > 0))]
            b += ["## Doğrulama: iş örneklemesi", "", "Model oranı (gercek) sahadaki %95 aralığın içinde mi?", "",
                  _md(k[["kaynak_tipi", "durum", "oran", "alt", "ust", "gercek", "aralikta"]].round(3)), ""]
        if uretim is not None:
            mt = pd.concat([r.tezgah for r in reps])
            b += ["## Doğrulama: m²/vardiya", "", _md(uretim_dogrulama(uretim, mt).round(1)), ""]
    b += ["## Parametre kaynakları", "", _md(p.tablo()), "", _md(p.tezgah_tablosu()), ""]
    return p, "\n".join(b)


def kos_tek(p: HaliParam, seed: int):
    from src.hali.model import kos
    return kos(p, seed)


def ornek_saha_verisi(klasor, p: HaliParam | None = None, seed: int = 99, gun: float = 5.0) -> None:
    """Modelden *sentetik* saha verisi üretir: formların ve analizin denenmesi için.

    Gerçek veri değildir; her satırın gozlemci sütunu SENTETIK yazılır.
    """
    from dataclasses import replace as _r
    from src.hali.model import kos
    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    p = _r(p or HaliParam(), sure_gun=gun)
    r = kos(p, seed)
    rng = np.random.default_rng(seed)
    isl = r.isler
    eleman = {"atki_kopusu": ("Atkı kopuşu düzeltme", "atki_mudahale"),
              "cozgu_kopusu": ("Çözgü/hav kopuşu düzeltme", "cozgu_mudahale"),
              "top_indirme": ("Top indirme", "top_indirme"), "ayar": ("Desen ayarı", "ayar"),
              "besleme": ("Bobin/cağlık besleme", "besleme_sure"), "kontrol": ("Halı kontrolü", "kontrol_sure")}
    z = []
    for tur, (ad, alan) in eleman.items():
        g = isl[isl["tur"] == tur].head(60)
        perf = rng.choice([90, 95, 100, 105, 110], len(g))
        for (_, s), pf in zip(g.iterrows(), perf):
            z.append({"tarih": "2026-12-01", "vardiya": 1, "gozlemci": "SENTETIK", "personel": s["personel"],
                      "tezgah": s["tezgah"], "eleman": ad, "model_alani": alan,
                      "sure_dk": round((s["bitis"] - s["baslama"]) * 100 / pf, 2), "performans": int(pf), "not": ""})
    pd.DataFrame(z).to_csv(klasor / "zaman_etudu.csv", index=False)
    o = sanal_is_ornekleme(r, int(gun * 3 * 3), seed)
    o.insert(0, "gozlemci", "SENTETIK")
    o.to_csv(klasor / "is_ornekleme.csv", index=False)
    k = isl[isl["tur"].isin(["atki_kopusu", "cozgu_kopusu"])]
    pd.DataFrame({"tarih": "2026-12-01", "tezgah": k["tezgah"], "tur": k["tur"].str.replace("_kopusu", ""),
                  "durus_dk": k["talep"].round(2), "mudahale_bas_dk": k["baslama"].round(2),
                  "bitis_dk": k["bitis"].round(2), "personel": k["personel"], "not": "SENTETIK"}
                 ).to_csv(klasor / "kopus_kayitlari.csv", index=False)
    d = [{"tarih": "2026-12-01", "saat": "", "tezgah": t.ad, "devir": round(t.devir.ornek(rng), 1), "not": "SENTETIK"}
         for t in p.tezgahlar for _ in range(30)]
    pd.DataFrame(d).to_csv(klasor / "devir_kayitlari.csv", index=False)
    vu = r.vardiya_uretim.assign(tarih="", m2=lambda x: x["m2"].round(1), **{"not": "SENTETIK"})
    vu.to_csv(klasor / "uretim_kayitlari.csv", index=False)
    (klasor / "OKU.txt").write_text(
        f"Bu klasördeki veriler modelden üretilmiş SENTETİK verilerdir ({gun:g} gün, tohum {seed}).\n"
        "Gerçek ölçüm değildir; formların ve `python -m src.hali.is_etudu analiz` komutunun denenmesi içindir.\n"
        f"Kopuş kaydı süresi: --kayit-saat {gun * 24:g}\n", encoding="utf-8")


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m src.hali.is_etudu", description="Halı salonu iş etüdü araçları")
    alt = ap.add_subparsers(dest="komut", required=True)
    pl = alt.add_parser("plan", help="rastgele iş örneklemesi tur planı")
    pl.add_argument("--baslangic", required=True, help="YYYY-AA-GG")
    pl.add_argument("--gun", type=int, default=10)
    pl.add_argument("--tur", type=int, default=3, help="vardiya başına tur")
    pl.add_argument("--vardiyalar", default="08:00,16:00,00:00")
    pl.add_argument("--seed", type=int, default=0)
    an = alt.add_parser("analiz", help="formları analiz et, parametreleri güncelle, modeli doğrula")
    an.add_argument("--klasor", default=str(FORM_KLASORU))
    an.add_argument("--parametre", default=None, help="başlangıç parametre JSON'u (yoksa varsayılan)")
    an.add_argument("--kayit-saat", type=float, default=None, help="kopuş/arıza kaydı süresi (saat)")
    an.add_argument("--dokuma-orani", type=float, default=None)
    so = alt.add_parser("ornek", help="denemek için sentetik saha verisi üret")
    so.add_argument("--klasor", default=str(FORM_KLASORU.parent / "ornek_saha"))
    a = ap.parse_args(argv)
    CIKTI.mkdir(parents=True, exist_ok=True)
    if a.komut == "plan":
        t = tur_plani(a.baslangic, a.gun, a.tur, tuple(a.vardiyalar.split(",")), seed=a.seed)
        t.to_csv(CIKTI / "tur_plani.csv", index=False)
        print(f"{len(t)} tur -> {CIKTI / 'tur_plani.csv'}")
        return
    if a.komut == "ornek":
        ornek_saha_verisi(a.klasor)
        print(f"Sentetik saha verisi -> {a.klasor}")
        return
    p0 = HaliParam.yukle(a.parametre) if a.parametre else HaliParam()
    p, rapor = analiz_et(a.klasor, p0, a.kayit_saat, a.dokuma_orani)
    (CIKTI / "is_etudu_analiz.md").write_text(rapor, encoding="utf-8")
    hedef = Path(a.klasor).parent / "parametreler_olcum.json"
    p.kaydet(hedef)
    print(f"Rapor -> {CIKTI / 'is_etudu_analiz.md'}\nParametreler -> {hedef}")


if __name__ == "__main__":
    main()
