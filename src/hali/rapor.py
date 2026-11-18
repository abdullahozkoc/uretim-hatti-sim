"""Halı salonu deney raporu: senaryolar, durum dağılımları, atama eğrisi,
zaman çizelgesi ve sanal iş örneklemesi. Çıktılar results/hali/ altına yazılır.

Çalıştırma:  python -m src.hali.rapor [replikasyon_sayısı]
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.analiz import guven_araligi  # noqa: E402
from src.hali import is_etudu as ie  # noqa: E402
from src.hali.model import ETIKET, kos  # noqa: E402
from src.hali.parametre import HaliParam  # noqa: E402
from src.hali.senaryo import (SENARYOLAR, TABAN_SEED, atama_egrisi, durum_ozeti, karsilastir,  # noqa: E402
                              senaryolari_kos)

CIKTI = Path(__file__).resolve().parents[2] / "results" / "hali"

# Durum -> renk (sabit sıra; aynı durum her grafikte aynı renk)
RENK = {
    "dokuma": "#2a78d6", "personel_bekleme": "#eb6834", "top_indirme": "#1baf7a",
    "atki_kopusu": "#eda100", "cozgu_degisimi": "#e87ba4", "cozgu_kopusu": "#008300",
    "ayar": "#6250d6", "ariza": "#e34948", "renk_degisimi": "#1f2d5c",
    "besleme": "#9c6b30", "kontrol": "#5b8fd1", "yurume": "#0e6e6e", "gozetim": "#b5b3ad", "mola": "#dcdad5",
}
TEZGAH_SIRA = ("dokuma", "personel_bekleme", "top_indirme", "atki_kopusu", "cozgu_degisimi",
               "cozgu_kopusu", "ayar", "renk_degisimi", "ariza")
PERSONEL_SIRA = ("kontrol", "besleme", "top_indirme", "atki_kopusu", "cozgu_kopusu", "ayar", "renk_degisimi",
                 "yurume", "gozetim", "mola")
OPERATOR_SIRA = PERSONEL_SIRA
ETIKET_KISA = {**ETIKET, "mola": "Mola + kişisel"}


def _stil(ax):
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    ax.spines["left"].set_color("#c3c2b7")
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")
    ax.grid(axis="x", color="#ecebe6", lw=0.8)
    ax.set_axisbelow(True)


def yigin_cubuk(tablo: pd.DataFrame, sira, baslik: str, yol: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(tablo) + 1.8))
    sol = pd.Series(0.0, index=tablo.index)
    for d in sira:
        ax.barh(tablo.index, tablo[d], left=sol, color=RENK[d], label=ETIKET_KISA[d],
                height=0.7, edgecolor="white", linewidth=1.2)
        sol += tablo[d]
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title(baslik, loc="left", fontsize=12, color="#0b0b0b")
    _stil(ax)
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.08), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def zaman_cizelgesi(sonuc, bas: float, sure: float, yol: Path) -> None:
    c = sonuc.cizelge
    c = c[(c["bit"] > bas) & (c["bas"] < bas + sure)].copy()
    c["durum"] = c["durum"].replace({"kisisel": "mola"})
    kaynaklar = []
    for t, o, tl in zip(sonuc.tezgah["tezgah"], sonuc.personel.query("rol=='operator'")["personel"],
                        sonuc.personel.query("rol=='telci'")["personel"]):
        kaynaklar += [t, o, tl]
    kaynaklar = list(dict.fromkeys(kaynaklar + list(sonuc.tezgah["tezgah"]) + list(sonuc.personel["personel"])))
    fig, ax = plt.subplots(figsize=(12, 0.32 * len(kaynaklar) + 1.8))
    for y, k in enumerate(kaynaklar):
        g = c[c["kaynak"] == k]
        segs = [(max(b, bas) - bas, min(e, bas + sure) - max(b, bas)) for b, e in zip(g["bas"], g["bit"])]
        ax.broken_barh(segs, (y - 0.38, 0.76), facecolors=[RENK[d] for d in g["durum"]], linewidth=0)
    ax.set_yticks(range(len(kaynaklar)), kaynaklar)
    ax.invert_yaxis()
    ax.set_xlim(0, sure)
    ax.set_xlabel("Vardiya içi süre (dk)", color="#52514e")
    ax.set_title("Bir vardiyanın zaman çizelgesi: her tezgâh, operatörü ve telcisi alt alta", loc="left", fontsize=12)
    _stil(ax)
    eller = [plt.Rectangle((0, 0), 1, 1, color=RENK[d]) for d in dict.fromkeys(TEZGAH_SIRA + PERSONEL_SIRA)]
    ax.legend(eller, [ETIKET_KISA[d] for d in dict.fromkeys(TEZGAH_SIRA + PERSONEL_SIRA)], ncol=5,
              loc="upper left", bbox_to_anchor=(0, -0.1), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def atama_grafigi(eg: pd.DataFrame, rol_ad: str, yol: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, (c, baslik, olcek) in zip(axes, (("m2_vardiya", "Salon üretimi (m²/vardiya)", 1),
                                             ("girisim", "Tezgâhın personel bekleme oranı (%)", 100),
                                             ("net_katki_vardiya", "Net katkı (bin TL/vardiya, VARSAYIM)", 1e-3))):
        ax.errorbar(eg["tezgah_kisi"], eg[c] * olcek, yerr=eg[c + "_yg"] * olcek, color="#2a78d6",
                    lw=2, marker="o", ms=7, mec="white", mew=1.5, capsize=3)
        ax.set_title(baslik, loc="left", fontsize=11)
        ax.set_xlabel(f"{rol_ad} başına tezgâh")
        ax.set_xticks(eg["tezgah_kisi"])
        _stil(ax)
        ax.grid(axis="y", color="#ecebe6", lw=0.8)
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def tezgah_uretim_grafigi(tz: pd.DataFrame, yol: Path) -> None:
    """Tezgâh başına m²/vardiya (H0, replikasyon ortalaması ± %95 GA)."""
    fig, ax = plt.subplots(figsize=(10, 3.8))
    x = range(len(tz))
    ax.bar(x, tz["ort"], color="#2a78d6", width=0.7, edgecolor="white", linewidth=1.2)
    ax.errorbar(x, tz["ort"], yerr=tz["yg"], fmt="none", ecolor="#52514e", capsize=3, lw=1)
    ax.set_xticks(list(x), [f"{t}\n{tr} tarak" for t, tr in zip(tz["tezgah"], tz["tarak"])], fontsize=8)
    ax.set_title("Tezgâh başına üretim (m²/vardiya, H0)", loc="left", fontsize=11)
    _stil(ax)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color="#ecebe6", lw=0.8)
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def yakinsama_grafigi(y: pd.DataFrame, yol: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for c, renk, ad in (("tezgah_maks_hata", "#2a78d6", "Tezgâh durumları"),
                        ("operator_maks_hata", "#eb6834", "Operatör durumları"),
                        ("telci_maks_hata", "#1baf7a", "Telci durumları")):
        ax.plot(y["tur"], y[c] * 100, color=renk, lw=2, marker="o", ms=7, mec="white", mew=1.5, label=ad)
    ax.set_xscale("log")
    ax.set_xticks(y["tur"], [str(t) for t in y["tur"]])
    ax.set_xlabel("Gözlem turu sayısı (her turda tüm kaynaklar gözlenir)")
    ax.set_title("Sanal iş örneklemesi: en büyük oran hatası (puan)", loc="left", fontsize=11)
    _stil(ax)
    ax.grid(axis="y", color="#ecebe6", lw=0.8)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def _md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def main(n: int = 20) -> None:
    CIKTI.mkdir(parents=True, exist_ok=True)
    p = HaliParam()
    p.kaydet(CIKTI.parent.parent / "data" / "hali" / "parametreler.json")
    sonuclar = senaryolari_kos(n=n)
    tablo = karsilastir(sonuclar)
    tablo.to_csv(CIKTI / "senaryo_karsilastirma.csv", index=False)
    tz = durum_ozeti(sonuclar, "tz:")
    op = durum_ozeti(sonuclar, "op:")
    tl = durum_ozeti(sonuclar, "tl:")
    for d in (op, tl):
        d["mola"] = d["mola"] + d.pop("kisisel")
    tz.round(4).to_csv(CIKTI / "tezgah_durumlari.csv")
    op.round(4).to_csv(CIKTI / "operator_durumlari.csv")
    tl.round(4).to_csv(CIKTI / "telci_durumlari.csv")
    for d in (tz, op, tl):
        d.index = [f"{k}: {SENARYOLAR[k][0]}" for k in d.index]
    yigin_cubuk(tz, TEZGAH_SIRA, "Tezgâh zamanının dağılımı (senaryo ortalaması)", CIKTI / "tezgah_durumlari.png")
    yigin_cubuk(op, PERSONEL_SIRA, "Operatör zamanının dağılımı", CIKTI / "operator_durumlari.png")
    yigin_cubuk(tl, PERSONEL_SIRA, "Telci zamanının dağılımı", CIKTI / "telci_durumlari.png")

    eg = atama_egrisi("telci", (1, 2, 3, 4), n=max(5, n // 2))
    eg.round(4).to_csv(CIKTI / "atama_egrisi_telci.csv", index=False)
    atama_grafigi(eg, "Telci", CIKTI / "atama_egrisi_telci.png")
    ego = atama_egrisi("operator", (1, 2, 3), n=max(5, n // 2))
    ego.round(4).to_csv(CIKTI / "atama_egrisi_operator.csv", index=False)
    atama_grafigi(ego, "Operatör", CIKTI / "atama_egrisi_operator.png")

    reps = [kos(p, TABAN_SEED + i) for i in range(min(n, 10))]
    tzr = pd.concat([r.tezgah for r in reps]).groupby(["tezgah", "tarak"], sort=False)["m2_vardiya"]
    tzu = tzr.apply(lambda x: pd.Series(dict(zip(("ort", "yg"), guven_araligi(x))))).unstack().reset_index()
    tzu.round(1).to_csv(CIKTI / "tezgah_uretim.csv", index=False)
    tezgah_uretim_grafigi(tzu, CIKTI / "tezgah_uretim.png")

    ornek = reps[0]
    zaman_cizelgesi(ornek, p.isinma_dk + 1440, p.vardiya_dk, CIKTI / "zaman_cizelgesi.png")
    yak = ie.yakinsama(ornek, tekrar=30)
    yak.round(4).to_csv(CIKTI / "is_ornekleme_yakinsama.csv", index=False)
    yakinsama_grafigi(yak, CIKTI / "is_ornekleme_yakinsama.png")

    p.tablo().to_csv(CIKTI / "parametreler.csv", index=False)
    p.tezgah_tablosu().to_csv(CIKTI / "tezgahlar.csv", index=False)
    rapor = f"""# Halı dokuma salonu: senaryo raporu

> Tezgâh bilgileri (marka, tarak, en, renk, tarak sayısı) ve personel düzeni fabrikadan gelir;
> devir, sıra sıklığı, kopuş, süre ve olasılıkların hepsi **VARSAYIM**dır. Sonuçlar yöntemi ve
> yönleri gösterir; sayılar iş etüdü ölçümleriyle güncellenince anlam kazanır.
> {n} replikasyon, 7 gün (+8 saat ısınma), ortak rastgele sayılar, %95 güven aralığı. Ana ölçüt m²/vardiya.

## Tezgâhlar

{_md(p.tezgah_tablosu()[["Tezgâh", "Marka", "Tarak (10 cm)", "En (m)", "Renk", "Tarak sayısı",
                          "Sıra (10 cm)", "Devir (/dk)", "Ort. m²/saat (kesintisiz)"]])}

![Tezgâh üretimi](tezgah_uretim.png)

## Senaryo karşılaştırması

{_md(tablo)}

Δ sütunu H0'a göre eşleştirilmiş farktır; aralık sıfırı içeriyorsa "(anlamsız)".

![Tezgâh durumları](tezgah_durumlari.png)

![Operatör durumları](operator_durumlari.png)

![Telci durumları](telci_durumlari.png)

## Kişi başına tezgâh sayısı (makine girişimi eğrisi)

Net katkı/vardiya = m²/vardiya × 60 TL − personel × 8 saat × 250 TL (ikisi de VARSAYIM).

### Telci

{_md(eg.drop(columns=[c for c in eg.columns if c.endswith("_yg")]).round(3))}

![Telci atama eğrisi](atama_egrisi_telci.png)

### Operatör

{_md(ego.drop(columns=[c for c in ego.columns if c.endswith("_yg")]).round(3))}

![Operatör atama eğrisi](atama_egrisi_operator.png)

## Bir vardiyanın zaman çizelgesi (H0, 2. gün ilk vardiya)

![Zaman çizelgesi](zaman_cizelgesi.png)

## Sanal iş örneklemesi: kaç gözlem turu yeter?

Her turda bütün tezgâhlar, operatörler ve telciler bir kez gözlenir
({int(yak['gozlem_tur_basina'].iloc[0])} gözlem/tur). Tablo, rastgele zamanlı turlarla tahmin edilen
oranların gerçek (simülasyondaki) orandan en çok kaç puan saptığını gösterir.

{_md(yak.round(3))}

![Yakınsama](is_ornekleme_yakinsama.png)
"""
    (CIKTI / "rapor.md").write_text(rapor, encoding="utf-8")
    print(tablo.to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
