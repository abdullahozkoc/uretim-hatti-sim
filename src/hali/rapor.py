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

from src.hali import is_etudu as ie  # noqa: E402
from src.hali.model import ETIKET, kos  # noqa: E402
from src.hali.parametre import HaliParam  # noqa: E402
from src.hali.senaryo import (SENARYOLAR, TABAN_SEED, atama_egrisi, durum_ozeti, karsilastir,  # noqa: E402
                              senaryolari_kos)

CIKTI = Path(__file__).resolve().parents[2] / "results" / "hali"

# Durum -> renk (sabit sıra; aynı durum her grafikte aynı renk)
RENK = {
    "dokuma": "#2a78d6", "operator_bekleme": "#eb6834", "top_indirme": "#1baf7a",
    "atki_kopusu": "#eda100", "cozgu_degisimi": "#e87ba4", "cozgu_kopusu": "#008300",
    "ayar": "#6250d6", "ariza": "#e34948",
    "besleme": "#9c6b30", "yurume": "#0e6e6e", "gozetim": "#b5b3ad", "mola": "#dcdad5",
}
TEZGAH_SIRA = ("dokuma", "operator_bekleme", "top_indirme", "atki_kopusu", "cozgu_degisimi",
               "cozgu_kopusu", "ayar", "ariza")
OPERATOR_SIRA = ("besleme", "top_indirme", "atki_kopusu", "cozgu_kopusu", "ayar", "yurume",
                 "gozetim", "mola")
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
    kaynaklar = list(dict.fromkeys(list(sonuc.operator["operator"]) + list(sonuc.tezgah["tezgah"])))
    fig, ax = plt.subplots(figsize=(12, 0.32 * len(kaynaklar) + 1.8))
    for y, k in enumerate(kaynaklar):
        g = c[c["kaynak"] == k]
        segs = [(max(b, bas) - bas, min(e, bas + sure) - max(b, bas)) for b, e in zip(g["bas"], g["bit"])]
        ax.broken_barh(segs, (y - 0.38, 0.76), facecolors=[RENK[d] for d in g["durum"]], linewidth=0)
    ax.set_yticks(range(len(kaynaklar)), kaynaklar)
    ax.invert_yaxis()
    ax.set_xlim(0, sure)
    ax.set_xlabel("Vardiya içi süre (dk)", color="#52514e")
    ax.set_title("Bir vardiyanın zaman çizelgesi: operatörler (üstte) ve tezgâhlar", loc="left", fontsize=12)
    _stil(ax)
    eller = [plt.Rectangle((0, 0), 1, 1, color=RENK[d]) for d in dict.fromkeys(TEZGAH_SIRA + OPERATOR_SIRA)]
    ax.legend(eller, [ETIKET_KISA[d] for d in dict.fromkeys(TEZGAH_SIRA + OPERATOR_SIRA)], ncol=5,
              loc="upper left", bbox_to_anchor=(0, -0.1), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def atama_grafigi(eg: pd.DataFrame, yol: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, (c, baslik, olcek) in zip(axes, (("m2_gun", "Üretim (m²/gün)", 1),
                                             ("girisim", "Tezgâhın operatör bekleme oranı (%)", 100),
                                             ("net_katki_gun", "Günlük net katkı (bin TL, VARSAYIM)", 1e-3))):
        ax.errorbar(eg["tezgah_operator"], eg[c] * olcek, yerr=eg[c + "_yg"] * olcek, color="#2a78d6",
                    lw=2, marker="o", ms=7, mec="white", mew=1.5, capsize=3)
        ax.set_title(baslik, loc="left", fontsize=11)
        ax.set_xlabel("Operatör başına tezgâh")
        ax.set_xticks(eg["tezgah_operator"])
        _stil(ax)
        ax.grid(axis="y", color="#ecebe6", lw=0.8)
        i = int(eg[c].idxmax())
        ax.annotate(f"{eg[c][i] * olcek:,.0f}" if olcek != 100 else f"%{eg[c][i] * 100:.1f}",
                    (eg["tezgah_operator"][i], eg[c][i] * olcek), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color="#52514e")
    fig.tight_layout()
    fig.savefig(yol, dpi=130, bbox_inches="tight")
    plt.close(fig)


def yakinsama_grafigi(y: pd.DataFrame, yol: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(y["tur"], y["operator_maks_hata"] * 100, color="#2a78d6", lw=2, marker="o", ms=7,
            mec="white", mew=1.5, label="Operatör durumları")
    ax.plot(y["tur"], y["tezgah_maks_hata"] * 100, color="#eb6834", lw=2, marker="o", ms=7,
            mec="white", mew=1.5, label="Tezgâh durumları")
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
    op["mola"] = op["mola"] + op.pop("kisisel")
    tz.round(4).to_csv(CIKTI / "tezgah_durumlari.csv")
    op.round(4).to_csv(CIKTI / "operator_durumlari.csv")
    tz.index = [f"{k}: {SENARYOLAR[k][0]}" for k in tz.index]
    op.index = [f"{k}: {SENARYOLAR[k][0]}" for k in op.index]
    yigin_cubuk(tz, TEZGAH_SIRA, "Tezgâh zamanının dağılımı (senaryo ortalaması)", CIKTI / "tezgah_durumlari.png")
    yigin_cubuk(op, OPERATOR_SIRA, "Operatör zamanının dağılımı (senaryo ortalaması)",
                CIKTI / "operator_durumlari.png")

    eg = atama_egrisi(n=max(5, n // 2))
    eg.round(4).to_csv(CIKTI / "atama_egrisi.csv", index=False)
    atama_grafigi(eg, CIKTI / "atama_egrisi.png")

    ornek = kos(p, TABAN_SEED)
    zaman_cizelgesi(ornek, p.isinma_dk + 1440, p.vardiya_dk, CIKTI / "zaman_cizelgesi.png")
    yak = ie.yakinsama(ornek, tekrar=40)
    yak.round(4).to_csv(CIKTI / "is_ornekleme_yakinsama.csv", index=False)
    yakinsama_grafigi(yak, CIKTI / "is_ornekleme_yakinsama.png")
    sanal = ie.sanal_is_ornekleme(ornek, 100, seed=1)
    sanal.to_csv(CIKTI / "sanal_is_ornekleme_100tur.csv", index=False)
    kars = ie.karsilastir(sanal, ie.gercek_oranlar(ornek))

    p.tablo().to_csv(CIKTI / "parametreler.csv", index=False)
    kars_g = kars[["kaynak_tipi", "durum", "gozlem", "oran", "alt", "ust", "gercek", "aralikta"]].round(3)
    rapor = f"""# Halı dokuma salonu: senaryo raporu

> Tüm parametreler **VARSAYIM**dır (fabrika verisi henüz yok). Sonuçlar yöntemi ve
> yönleri gösterir; sayılar iş etüdü ölçümleriyle güncellenince anlam kazanır.
> {n} replikasyon, 7 gün (+8 saat ısınma), ortak rastgele sayılar, %95 güven aralığı.

## Senaryo karşılaştırması

{_md(tablo)}

Δ sütunu H0'a göre eşleştirilmiş farktır; aralık sıfırı içeriyorsa "(anlamsız)".

![Tezgâh durumları](tezgah_durumlari.png)

![Operatör durumları](operator_durumlari.png)

## Operatör başına tezgâh sayısı (makine girişimi eğrisi)

Net katkı = m²/gün × 60 TL − operatör sayısı × 24 saat × 250 TL (ikisi de VARSAYIM).

{_md(eg[["tezgah_operator", "operator_sayisi", "m2_gun", "tezgah_verimi", "girisim", "operator_doluluk",
         "m2_operator_saat", "net_katki_gun"]].round(3))}

![Atama eğrisi](atama_egrisi.png)

## Bir vardiyanın zaman çizelgesi (H0, 2. gün ilk vardiya)

![Zaman çizelgesi](zaman_cizelgesi.png)

## Sanal iş örneklemesi: kaç gözlem turu yeter?

Her turda bütün operatörler ve tezgâhlar bir kez gözlenir. Tablo, rastgele zamanlı
turlarla tahmin edilen oranların gerçek (simülasyondaki) orandan en çok ne kadar
saptığını gösterir.

{_md(yak.round(3))}

![Yakınsama](is_ornekleme_yakinsama.png)

100 turluk bir örnekleme ile gerçek oranların karşılaştırması (sahada model doğrulaması
aynı tabloyla yapılır):

{_md(kars_g)}
"""
    (CIKTI / "rapor.md").write_text(rapor, encoding="utf-8")
    print(tablo.to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
