"""Gerçek veriyle kalibrasyon (Bölüm 13): dağılım uydurma ve uyum testi.

Kullanım:
    import numpy as np
    from src.kalibrasyon import dagilim_uydur, istasyon_param_olustur, mtbf_mttr
    sureler = np.loadtxt("data/istasyon3_sureler.csv")
    tablo = dagilim_uydur(sureler)          # adaylar, KS istatistiği ve p değeri
    ist = istasyon_param_olustur("İstasyon 3", sureler, ariza_kayitlari=...)

Not: Kolmogorov-Smirnov p değeri, parametreler aynı veriden tahmin edildiği
için iyimserdir; karar verirken histogram ile birlikte yorumlanmalıdır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.hat import IstasyonParam

ADAYLAR = {
    "normal": stats.norm,
    "ucgen": stats.triang,
    "ustel": stats.expon,
    "lognormal": stats.lognorm,
    "gamma": stats.gamma,
}


def dagilim_uydur(veri, adaylar=("normal", "ucgen", "ustel", "lognormal", "gamma")) -> pd.DataFrame:
    """Aday dağılımları en çok olabilirlikle uydurur, KS testine göre sıralar."""
    x = np.asarray(veri, dtype=float)
    if x.size < 30:
        raise ValueError("Dağılım uydurmak için en az 30 gözlem gerekir (önerilen 100-200).")
    satirlar = []
    for ad in adaylar:
        dist = ADAYLAR[ad]
        kw = {"floc": 0} if ad in ("lognormal", "gamma") else {}
        par = dist.fit(x, **kw)
        ks = stats.kstest(x, dist.cdf, args=par)
        satirlar.append({"dagilim": ad, "parametreler": tuple(float(p) for p in par),
                         "ks_istatistigi": ks.statistic, "p_degeri": ks.pvalue,
                         "ortalama": float(dist.mean(*par))})
    return pd.DataFrame(satirlar).sort_values("ks_istatistigi").reset_index(drop=True)


def mtbf_mttr(ariza_baslangic, ariza_bitis) -> tuple[float, float]:
    """Sıralı arıza başlangıç/bitiş zamanlarından MTBF ve MTTR (aynı birimde)."""
    b = np.asarray(ariza_baslangic, dtype=float)
    e = np.asarray(ariza_bitis, dtype=float)
    if b.size < 2 or b.size != e.size:
        raise ValueError("En az iki arıza kaydı ve eşit uzunlukta başlangıç/bitiş gerekir.")
    mttr = float(np.mean(e - b))
    calisma_araliklari = b[1:] - e[:-1]          # onarım bitişinden sonraki arızaya
    return float(np.mean(calisma_araliklari)), mttr


def istasyon_param_olustur(ad: str, sureler, ariza_kayitlari=None, tampon=5,
                           kapasite=1) -> IstasyonParam:
    """Ölçülen sürelere en iyi uyan (modelin desteklediği) dağılımla istasyon üretir."""
    x = np.asarray(sureler, dtype=float)
    tablo = dagilim_uydur(x, adaylar=("normal", "ucgen", "ustel"))
    en_iyi = tablo.iloc[0]
    mtbf = mttr = None
    if ariza_kayitlari is not None:
        mtbf, mttr = mtbf_mttr(*ariza_kayitlari)
    ortak = dict(mtbf=mtbf, mttr=mttr or 0.0, tampon=tampon, kapasite=kapasite)
    if en_iyi["dagilim"] == "normal":
        mu, sigma = en_iyi["parametreler"]
        return IstasyonParam(ad, mu, "normal", sigma=sigma, **ortak)
    if en_iyi["dagilim"] == "ucgen":
        c, loc, scale = en_iyi["parametreler"]
        ucg = (loc, loc + c * scale, loc + scale)
        return IstasyonParam(ad, sum(ucg) / 3, "ucgen", ucgen=ucg, **ortak)
    return IstasyonParam(ad, float(x.mean()), "ustel", **ortak)
