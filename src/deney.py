"""Deney katmanı: replikasyon, senaryo karşılaştırma, Welch ısınma analizi.

Çalıştırma:  python -m src.deney      (sonuçlar results/ klasörüne yazılır)
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from src.analiz import bicimle, eslestirilmis_fark, guven_araligi, hareketli_ortalama
from src.hat import HatParam, kos, temel_hat

TABAN_SEED = 2026
SONUC_DIZINI = Path(__file__).resolve().parent.parent / "results"


# ---------------------------------------------------------------- senaryolar
def _s1(p: HatParam) -> HatParam:          # darboğaza ikinci operatör
    return p.istasyon_degistir(2, kapasite=2)


def _s2(p: HatParam) -> HatParam:          # tüm ara stoklar 5 -> 10
    return p.tum_tamponlar(10)


def _s3(p: HatParam) -> HatParam:          # hat dengeleme
    # İstasyon 3'ten ~0,4 dk iş alınır (üçgen dağılım 0,4 sola kayar),
    # İstasyon 1 ve 5'e 0,2'şer dk eklenir.
    p = p.istasyon_degistir(2, ort=2.2, ucgen=(1.6, 2.2, 3.0))
    p = p.istasyon_degistir(0, ort=p.istasyonlar[0].ort + 0.2)
    return p.istasyon_degistir(4, ort=p.istasyonlar[4].ort + 0.2)


def _s4(p: HatParam) -> HatParam:          # önleyici bakım: İst. 3 MTBF 180 -> 300
    return p.istasyon_degistir(2, mtbf=300)


SENARYOLAR: dict[str, tuple[str, Callable[[HatParam], HatParam]]] = {
    "S0": ("Temel durum", lambda p: p),
    "S1": ("Darboğaza ikinci operatör", _s1),
    "S2": ("Tampon büyütme (5→10)", _s2),
    "S3": ("Hat dengeleme", _s3),
    "S4": ("Arıza azaltma (MTBF 180→300)", _s4),
}


def senaryo_param(kod: str, temel: HatParam | None = None) -> HatParam:
    return SENARYOLAR[kod][1](temel or temel_hat())


# ---------------------------------------------------------------- replikasyon
def _tek(args) -> dict:
    p, seed = args
    r = kos(p, seed)
    satir = dict(r.ozet)
    for _, s in r.istasyon.iterrows():
        satir[f"kullanim:{s['istasyon']}"] = s["kullanim"]
        for d in ("calisma", "bos", "bloklu", "ariza"):
            satir[f"{d}:{s['istasyon']}"] = s[d]
    return satir


def replikasyon(p: HatParam, n: int = 30, taban_seed: int = TABAN_SEED,
                paralel: bool = False, ilerleme: Callable[[float], None] | None = None) -> pd.DataFrame:
    """n replikasyon; replikasyon i için tohum = taban + i (ortak rastgele sayılar)."""
    isler = [(p, taban_seed + i) for i in range(n)]
    if paralel:
        with ProcessPoolExecutor() as h:
            satirlar = list(h.map(_tek, isler))
    else:
        satirlar = []
        for k, is_ in enumerate(isler):
            satirlar.append(_tek(is_))
            if ilerleme:
                ilerleme((k + 1) / n)
    return pd.DataFrame(satirlar)


def ozetle(df: pd.DataFrame) -> dict:
    """Bir senaryonun replikasyon tablosundan ortalama ± %95 YG özetleri."""
    o = {"n": len(df)}
    for m in ("verim", "cevrim_suresi", "wip", "tampon_wip"):
        o[m], o[m + "_yg"] = guven_araligi(df[m])
    sayac = Counter(df["darbogaz"])
    o["darbogaz"], adet = sayac.most_common(1)[0]
    o["darbogaz_payi"] = adet / len(df)
    kullanim = {c.split(":", 1)[1]: df[c].mean() for c in df.columns if c.startswith("kullanim:")}
    o["kullanim"] = kullanim
    return o


def karsilastir(sonuclar: dict[str, pd.DataFrame], referans: str = "S0") -> pd.DataFrame:
    """Senaryo karşılaştırma tablosu (Bölüm 9) ve S0'a göre eşleştirilmiş farklar."""
    satirlar = []
    ref = sonuclar[referans]
    for kod, df in sonuclar.items():
        o = ozetle(df)
        satir = {
            "Senaryo": kod,
            "Açıklama": SENARYOLAR.get(kod, (kod,))[0],
            "n": o["n"],
            "Verim (ürün/saat)": bicimle(o["verim"], o["verim_yg"]),
            "Çevrim süresi (dk)": bicimle(o["cevrim_suresi"], o["cevrim_suresi_yg"], 1),
            "Ortalama WIP": bicimle(o["wip"], o["wip_yg"]),
            "Darboğaz": f"{o['darbogaz']} (%{100 * o['darbogaz_payi']:.0f})",
        }
        if kod != referans:
            for m, etiket, b in (("verim", "Δ verim", 2), ("wip", "Δ WIP", 2),
                                 ("cevrim_suresi", "Δ çevrim", 1)):
                f = eslestirilmis_fark(ref[m], df[m])
                satir[etiket] = f"{f['fark']:+.{b}f} [{f['alt']:+.{b}f}, {f['ust']:+.{b}f}]" + \
                    ("" if f["anlamli"] else " (anlamsız)")
        else:
            satir.update({"Δ verim": "-", "Δ WIP": "-", "Δ çevrim": "-"})
        satirlar.append(satir)
    return pd.DataFrame(satirlar)


def senaryolari_kos(kodlar=("S0", "S1", "S2", "S3", "S4"), n: int = 30,
                    temel: HatParam | None = None, paralel: bool = True,
                    taban_seed: int = TABAN_SEED) -> dict[str, pd.DataFrame]:
    return {k: replikasyon(senaryo_param(k, temel), n, taban_seed, paralel) for k in kodlar}


# ---------------------------------------------------------------- Welch
def welch(p: HatParam, n: int = 30, sure: float = 3_000.0, w: int = 10,
          metrik: str = "wip", tolerans: float = 0.05, taban_seed: int = TABAN_SEED) -> dict:
    """Welch yöntemi: ısınmasız uzun koşulardan dilim ortalamaları ve önerilen ısınma.

    Kararlı değer serinin son yarısının ortalamasıdır; önerilen ısınma,
    hareketli ortalamanın kararlı değerin ±tolerans bandına ilk girdiği andır.
    Seçilen ısınma, güvenlik payı için bunun birkaç katı alınmalıdır.
    """
    q = replace(p, isinma=0.0, sure=sure)
    seriler = [kos(q, taban_seed + i).zaman_serisi[metrik].to_numpy(float) for i in range(n)]
    uzunluk = min(len(s) for s in seriler)
    ort = np.mean([s[:uzunluk] for s in seriler], axis=0)
    ma = hareketli_ortalama(ort, w)
    t = (np.arange(len(ma)) + 1) * p.dilim
    kararli = ma[len(ma) // 2:].mean()
    # Geçiş döneminin bitişi: hareketli ortalamanın kararlı değerin ±tolerans
    # bandına ilk girdiği an. ("Bir daha hiç çıkmadığı an" kuralı, kararlı
    # durumdaki rastgele dalgalanmayı da geçiş sanıp ısınmayı abartıyor.)
    icinde = np.where(np.abs(ma - kararli) <= tolerans * abs(kararli))[0]
    isinma = float(t[icinde[0]]) if icinde.size else float(t[-1])
    return {"t": t, "ortalama": ort[:len(ma)], "hareketli": ma, "kararli": kararli,
            "onerilen_isinma": isinma, "metrik": metrik, "n": n, "w": w}


# ---------------------------------------------------------------- yeni hedefler
def gerekli_replikasyon(p: HatParam, metrik: str = "verim", hedef_oran: float = 0.01,
                        n0: int = 10, n_maks: int = 300, taban_seed: int = TABAN_SEED) -> dict:
    """Hedef bağıl yarı genişliğe (ör. ortalamanın %1'i) ulaşmak için replikasyon sayısı.

    Pilot n0 replikasyondan s tahmin edilir, n* = (t·s / (hedef·x̄))² hesaplanır,
    eksik replikasyonlar koşulup hedef tutana kadar tekrarlanır.
    """
    df = replikasyon(p, n0, taban_seed)
    while True:
        ort, yg = guven_araligi(df[metrik])
        if yg <= hedef_oran * abs(ort) or len(df) >= n_maks:
            return {"n": len(df), "ortalama": ort, "yg": yg, "bagil_yg": yg / abs(ort),
                    "hedef": hedef_oran, "veri": df}
        s = df[metrik].std(ddof=1)
        tahmin = int(np.ceil((1.96 * s / (hedef_oran * abs(ort))) ** 2))
        yeni_n = min(max(tahmin, len(df) + 5), n_maks)
        ek = replikasyon(p, yeni_n - len(df), taban_seed + len(df))
        df = pd.concat([df, ek], ignore_index=True)


def tampon_duyarlilik(kapasiteler=(1, 2, 3, 5, 8, 10, 15, 20), n: int = 30,
                      temel: HatParam | None = None, taban_seed: int = TABAN_SEED) -> pd.DataFrame:
    """Tüm ara stok kapasiteleri k iken verim ve WIP (tampon-verim eğrisi)."""
    temel = temel or temel_hat()
    satirlar = []
    for k in kapasiteler:
        df = replikasyon(temel.tum_tamponlar(k), n, taban_seed, paralel=True)
        v, vy = guven_araligi(df["verim"])
        w, wy = guven_araligi(df["wip"])
        c, cy = guven_araligi(df["cevrim_suresi"])
        satirlar.append({"tampon": k, "verim": v, "verim_yg": vy, "wip": w, "wip_yg": wy,
                         "cevrim_suresi": c, "cevrim_suresi_yg": cy})
    return pd.DataFrame(satirlar)


# ---------------------------------------------------------------- rapor
def main(n: int = 30) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SONUC_DIZINI.mkdir(exist_ok=True)
    temel = temel_hat()

    # 1) Welch
    wv = welch(temel, n=n, metrik="wip")
    wc = welch(temel, n=n, metrik="cikis", tolerans=0.10)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for a, wr, baslik in ((ax[0], wv, "Hattaki WIP"), (ax[1], wc, "10 dk'da çıkan ürün")):
        a.plot(wr["t"], wr["ortalama"], color="#bbb", lw=0.8, label="replikasyon ortalaması")
        a.plot(wr["t"], wr["hareketli"], color="#1f6feb", lw=1.8, label=f"hareketli ort. (w={wr['w']})")
        a.axvline(wr["onerilen_isinma"], color="#d1242f", ls="--", label=f"önerilen ısınma ≈ {wr['onerilen_isinma']:.0f} dk")
        a.axvline(temel.isinma, color="#555", ls=":", label=f"kullanılan ısınma = {temel.isinma:.0f} dk")
        a.set_title(f"Welch: {baslik} ({wr['n']} replikasyon)")
        a.set_xlabel("zaman (dk)")
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(SONUC_DIZINI / "welch.png", dpi=130)
    plt.close(fig)

    # 2) Senaryolar
    sonuclar = senaryolari_kos(n=n)
    tablo = karsilastir(sonuclar)
    pd.concat([d.assign(senaryo=k) for k, d in sonuclar.items()]).to_csv(
        SONUC_DIZINI / "senaryo_replikasyonlari.csv", index=False)
    tablo.to_csv(SONUC_DIZINI / "senaryo_karsilastirma.csv", index=False)

    kullanim = pd.DataFrame({k: ozetle(d)["kullanim"] for k, d in sonuclar.items()})
    durum = {}
    for k, d in sonuclar.items():
        durum[k] = {dd: {c.split(":", 1)[1]: d[c].mean() for c in d.columns if c.startswith(dd + ":")}
                    for dd in ("calisma", "ariza", "bloklu", "bos")}
    fig, axs = plt.subplots(1, len(sonuclar), figsize=(3.2 * len(sonuclar), 3.6), sharey=True)
    renk = {"calisma": "#2da44e", "ariza": "#d1242f", "bloklu": "#bf8700", "bos": "#8c959f"}
    for a, (k, dd) in zip(axs, durum.items()):
        alt = np.zeros(5)
        adlar = list(dd["calisma"].keys())
        for durum_adi in ("calisma", "ariza", "bloklu", "bos"):
            v = np.array([dd[durum_adi][i] for i in adlar])
            a.bar(range(1, 6), v, bottom=alt, color=renk[durum_adi], label=durum_adi)
            alt += v
        a.set_title(k)
        a.set_xticks(range(1, 6))
        a.set_xlabel("istasyon")
    axs[0].set_ylabel("zaman payı")
    axs[-1].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(SONUC_DIZINI / "istasyon_durumlari.png", dpi=130)
    plt.close(fig)

    # 3) Tampon duyarlılığı (yeni hedef)
    td = tampon_duyarlilik(n=n)
    td.to_csv(SONUC_DIZINI / "tampon_duyarlilik.csv", index=False)
    fig, a1 = plt.subplots(figsize=(6, 3.6))
    a1.errorbar(td["tampon"], td["verim"], yerr=td["verim_yg"], marker="o", color="#1f6feb", label="verim")
    a1.set_xlabel("ara stok kapasitesi (tüm tamponlar)")
    a1.set_ylabel("verim (ürün/saat)", color="#1f6feb")
    a2 = a1.twinx()
    a2.errorbar(td["tampon"], td["wip"], yerr=td["wip_yg"], marker="s", color="#bf8700", label="WIP")
    a2.set_ylabel("ortalama WIP", color="#bf8700")
    a1.set_title("Tampon kapasitesi – verim – WIP")
    fig.tight_layout()
    fig.savefig(SONUC_DIZINI / "tampon_duyarlilik.png", dpi=130)
    plt.close(fig)

    # 4) Gereken replikasyon sayısı (yeni hedef)
    gr = gerekli_replikasyon(temel, "verim", 0.01)

    # Markdown rapor
    md = ["# Deney sonuçları", "",
          f"Koşu: {temel.sure:.0f} dk ölçüm + {temel.isinma:.0f} dk ısınma, her senaryo {n} replikasyon, "
          f"tohumlar {TABAN_SEED}..{TABAN_SEED + n - 1} (tüm senaryolarda ortak). Aralıklar %95 güven aralığıdır; "
          "Δ sütunları S0'a göre eşleştirilmiş farktır.", "",
          tablo.to_markdown(index=False), "",
          "## İstasyon kullanım oranları (çalışma + arıza)", "",
          (kullanim * 100).round(1).to_markdown(), "",
          "## Welch ısınma analizi", "",
          f"- WIP serisi: önerilen ısınma ≈ {wv['onerilen_isinma']:.0f} dk (kararlı WIP ≈ {wv['kararli']:.2f})",
          f"- Çıkış serisi: önerilen ısınma ≈ {wc['onerilen_isinma']:.0f} dk",
          f"- Kullanılan ısınma: {temel.isinma:.0f} dk; iki serinin de geçiş döneminin "
          f"yaklaşık {temel.isinma / max(wv['onerilen_isinma'], wc['onerilen_isinma']):.1f} katı, "
          "yani dokümandaki 500 dk kararı güvenli tarafta.", "",
          "![Welch](welch.png)", "", "![İstasyon durumları](istasyon_durumlari.png)", "",
          "## Tampon duyarlılığı", "", td.round(2).to_markdown(index=False), "",
          "![Tampon duyarlılığı](tampon_duyarlilik.png)", "",
          "## Gereken replikasyon sayısı", "",
          f"S0 verimi için %1 bağıl yarı genişlik hedefi: **{gr['n']} replikasyon** "
          f"(verim {gr['ortalama']:.2f} ± {gr['yg']:.2f}, bağıl %{100 * gr['bagil_yg']:.2f}).", ""]
    (SONUC_DIZINI / "deney_raporu.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
