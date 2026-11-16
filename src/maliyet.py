"""Ekonomik değerlendirme: senaryoların verim kazancını paraya çevirir.

Her senaryo için replikasyon bazında (ortak rastgele sayılar) yıllık net fayda
hesaplanır ve %95 güven aralığıyla raporlanır:

    yıllık net fayda = [Δverim · birim katkı payı
                        − ΔWIP · WIP taşıma maliyeti
                        − ek saatlik işletme maliyeti] · yıllık çalışma saati
                       − ek yıllık sabit maliyet

Ardından geri ödeme süresi, net bugünkü değer (NBD) ve başabaş birim katkı
payı (yatırımın ufuk içinde geri dönmesi için ürün başına gereken en düşük
katkı) hesaplanır.

ÖNEMLİ: Varsayılan tutarlar ÖRNEKTİR, gerçek şirket verisi değildir. Gerçek
değerler maliyet muhasebesi ve satın alma birimlerinden alınmalıdır.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.analiz import guven_araligi


@dataclass(frozen=True)
class SenaryoMaliyeti:
    yatirim: float = 0.0            # bir kerelik yatırım (TL)
    saatlik: float = 0.0            # ek işletme maliyeti (TL/saat), ör. operatör ücreti
    yillik: float = 0.0             # ek sabit yıllık maliyet (TL/yıl), ör. bakım sözleşmesi
    aciklama: str = ""


@dataclass(frozen=True)
class MaliyetParam:
    birim_katki: float = 150.0          # ürün başına katkı payı (satış - değişken maliyet), TL
    wip_tasima: float = 2.0             # bir WIP parçasının saatlik taşıma maliyeti, TL/saat
    yillik_saat: float = 4_000.0        # 2 vardiya x 8 saat x 250 gün
    ufuk: int = 3                       # değerlendirme ufku, yıl
    iskonto: float = 0.30               # yıllık iskonto oranı
    operator_saatlik: float = 250.0     # bir operatörün işverene saatlik maliyeti, TL
    tampon_slot_yatirim: float = 20_000.0  # bir ara stok yerinin (raf/konveyör) yatırımı, TL
    dengeleme_yatirim: float = 400_000.0   # S3: iş bölümü, aparat ve yeniden yerleşim, TL
    bakim_yillik: float = 300_000.0        # S4: önleyici bakım programı, TL/yıl
    operator_yatirim: float = 150_000.0    # S1: ikinci iş yeri ekipmanı ve eğitim, TL

    def senaryo_maliyetleri(self, ek_tampon_slot: int = 20) -> dict[str, SenaryoMaliyeti]:
        """Dokümandaki S1-S4 senaryolarının maliyet karşılıkları."""
        return {
            "S0": SenaryoMaliyeti(aciklama="Referans"),
            "S1": SenaryoMaliyeti(self.operator_yatirim, self.operator_saatlik,
                                  aciklama="İkinci operatör: ekipman + eğitim, saatlik ücret"),
            "S2": SenaryoMaliyeti(ek_tampon_slot * self.tampon_slot_yatirim,
                                  aciklama=f"{ek_tampon_slot} ek ara stok yeri"),
            "S3": SenaryoMaliyeti(self.dengeleme_yatirim, aciklama="Hat dengeleme projesi"),
            "S4": SenaryoMaliyeti(yillik=self.bakim_yillik, aciklama="Önleyici bakım programı"),
        }


def _nbd(yatirim: float, yillik_fayda, iskonto: float, ufuk: int):
    carpan = sum(1 / (1 + iskonto) ** t for t in range(1, ufuk + 1))
    return -yatirim + np.asarray(yillik_fayda) * carpan, carpan


def degerlendir(sonuclar: dict[str, pd.DataFrame], maliyet: MaliyetParam | None = None,
                senaryo_maliyetleri: dict[str, SenaryoMaliyeti] | None = None,
                referans: str = "S0") -> pd.DataFrame:
    """Her senaryo için yıllık net fayda, geri ödeme, NBD ve başabaş katkı payı."""
    m = maliyet or MaliyetParam()
    sm = senaryo_maliyetleri or m.senaryo_maliyetleri()
    ref = sonuclar[referans]
    satirlar = []
    for kod, df in sonuclar.items():
        if kod == referans:
            continue
        c = sm.get(kod, SenaryoMaliyeti())
        dv = df["verim"].to_numpy() - ref["verim"].to_numpy()        # ürün/saat
        dw = df["wip"].to_numpy() - ref["wip"].to_numpy()
        saatlik = dv * m.birim_katki - dw * m.wip_tasima - c.saatlik
        yillik = saatlik * m.yillik_saat - c.yillik
        f, f_yg = guven_araligi(yillik)
        nbd, carpan = _nbd(c.yatirim, yillik, m.iskonto, m.ufuk)
        n_ort, n_yg = guven_araligi(nbd)
        # Başabaş: NBD = 0 yapan birim katkı payı (ortalama Δ'lar üzerinden)
        dv_ort = dv.mean()
        sabit = (dw.mean() * m.wip_tasima + c.saatlik) * m.yillik_saat + c.yillik
        basabas = ((c.yatirim / carpan + sabit) / (dv_ort * m.yillik_saat)
                   if dv_ort > 0 else float("inf"))
        satirlar.append({
            "Senaryo": kod,
            "Maliyet kalemi": c.aciklama,
            "Yatırım (TL)": c.yatirim,
            "Δ verim (ürün/saat)": dv_ort,
            "Yıllık net fayda (TL)": f,
            "Yıllık net fayda YG ±": f_yg,
            "Geri ödeme (ay)": (12 * c.yatirim / f if f > 0 else float("inf")) if c.yatirim else 0.0,
            f"NBD {m.ufuk} yıl (TL)": n_ort,
            "NBD YG ±": n_yg,
            "NBD > 0 olan replikasyon": float((nbd > 0).mean()),
            "Başabaş katkı payı (TL/ürün)": basabas,
        })
    return pd.DataFrame(satirlar).sort_values(f"NBD {m.ufuk} yıl (TL)", ascending=False,
                                              ignore_index=True)


def duyarlilik(sonuclar: dict[str, pd.DataFrame], katkilar=(25, 50, 75, 100, 150, 200, 300),
               maliyet: MaliyetParam | None = None) -> pd.DataFrame:
    """Birim katkı payı değiştikçe her senaryonun NBD'si (en iyi seçimin kararlılığı)."""
    from dataclasses import replace
    m = maliyet or MaliyetParam()
    satirlar = []
    for k in katkilar:
        d = degerlendir(sonuclar, replace(m, birim_katki=float(k)))
        satir = {"Birim katkı (TL)": k}
        satir.update({r["Senaryo"]: r[f"NBD {m.ufuk} yıl (TL)"] for _, r in d.iterrows()})
        satir["En iyi"] = d.iloc[0]["Senaryo"] if d.iloc[0][f"NBD {m.ufuk} yıl (TL)"] > 0 else "Hiçbiri"
        satirlar.append(satir)
    return pd.DataFrame(satirlar)


def tablo_bicimle(d: pd.DataFrame) -> pd.DataFrame:
    """Rapor ve panel için okunur biçim."""
    ufuk_kol = [c for c in d.columns if c.startswith("NBD ") and c.endswith("(TL)")][0]

    def tl(x):
        return "∞" if not np.isfinite(x) else f"{x:,.0f}".replace(",", ".")

    return pd.DataFrame({
        "Senaryo": d["Senaryo"],
        "Maliyet kalemi": d["Maliyet kalemi"],
        "Yatırım (TL)": d["Yatırım (TL)"].map(tl),
        "Yıllık net fayda (TL)": [f"{tl(a)} ± {tl(b)}" for a, b in
                                   zip(d["Yıllık net fayda (TL)"], d["Yıllık net fayda YG ±"])],
        "Geri ödeme (ay)": d["Geri ödeme (ay)"].map(lambda x: "∞" if not np.isfinite(x) else
                                                    ("yatırım yok" if x == 0 else f"{x:.1f}")),
        ufuk_kol: [f"{tl(a)} ± {tl(b)}" for a, b in zip(d[ufuk_kol], d["NBD YG ±"])],
        "NBD > 0 olan replikasyon": d["NBD > 0 olan replikasyon"].map(lambda x: f"%{100 * x:.0f}"),
        "Başabaş katkı (TL/ürün)": d["Başabaş katkı payı (TL/ürün)"].map(
            lambda x: "∞" if not np.isfinite(x) else f"{x:.0f}"),
    })


def secim_gecisleri(sonuclar: dict[str, pd.DataFrame], maliyet: MaliyetParam | None = None,
                    alt: float = 5.0, ust: float = 400.0, adim: float = 1.0) -> list[tuple[float, str]]:
    """Birim katkı payı arttıkça en iyi senaryonun değiştiği noktalar [(katkı, yeni en iyi)]."""
    m = maliyet or MaliyetParam()
    d = duyarlilik(sonuclar, np.arange(alt, ust + adim, adim), m)
    gecis, onceki = [], None
    for _, r in d.iterrows():
        if r["En iyi"] != onceki:
            gecis.append((float(r["Birim katkı (TL)"]), r["En iyi"]))
            onceki = r["En iyi"]
    return gecis
