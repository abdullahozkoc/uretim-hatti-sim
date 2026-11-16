"""Streamlit paneli: parametreleri değiştir, sonuçları güven aralığıyla gör.

Çalıştırma:  streamlit run app/panel.py
"""
from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.analiz import eslestirilmis_fark, guven_araligi  # noqa: E402
from src.deney import SENARYOLAR, karsilastir, ozetle, replikasyon, senaryo_param  # noqa: E402
from src.hat import HatParam, kos  # noqa: E402

st.set_page_config(page_title="Üretim Hattı Simülasyonu", layout="wide")


@st.cache_data(show_spinner=False)
def _replikasyon(p: HatParam, n: int, seed: int) -> pd.DataFrame:
    # Panel tek süreçte koşar: Streamlit içinde süreç havuzu güvenilir değil.
    return replikasyon(p, n, seed, paralel=False)


@st.cache_data(show_spinner=False)
def _ornek_kosu(p: HatParam, seed: int):
    r = kos(p, seed)
    return r.zaman_serisi, r.tampon


# ---------------------------------------------------------------- kenar çubuğu
sb = st.sidebar
sb.title("Parametreler")
hazir = sb.selectbox("Senaryo hazır ayarı", list(SENARYOLAR),
                     format_func=lambda k: f"{k}: {SENARYOLAR[k][0]}")
n = sb.slider("Replikasyon sayısı", 10, 100, 30, step=5)
sure = sb.select_slider("Koşu uzunluğu (dk, ısınma hariç)", [1_000, 2_000, 5_000, 10_000], 5_000)
isinma = sb.number_input("Isınma süresi (dk)", 0, 2_000, 500, step=100)
seed = int(sb.number_input("Taban rastgele tohum", 0, 10**6, 2026))
ariza = sb.checkbox("Arızalar açık", True)

taban = senaryo_param(hazir)
sb.subheader("İstasyonlar")
istasyonlar = []
for i, ist in enumerate(taban.istasyonlar):
    with sb.expander(ist.ad, expanded=False):
        k = f"{hazir}-{i}"
        varsayilan = float(round(ist.ortalama_sure, 2))
        ort = st.slider("Ortalama işlem süresi (dk)", 0.5, 5.0, varsayilan, 0.05, key=k + "o")
        mtbf = st.slider("Arıza aralığı MTBF (dk)", 30, 1_000, int(ist.mtbf or 1_000), 10, key=k + "m")
        mttr = st.slider("Onarım süresi MTTR (dk)", 0, 60, int(ist.mttr), 1, key=k + "r")
        kap = st.slider("Kaynak sayısı", 1, 3, ist.kapasite, key=k + "k")
        tampon = ist.tampon
        if i < len(taban.istasyonlar) - 1:
            tampon = st.slider("Sonraki ara stok kapasitesi", 1, 20, ist.tampon, key=k + "t")
        # Ortalama değişirse dağılım şekli korunur, yalnızca kaydırılır.
        kayma = 0.0 if ort == varsayilan else ort - ist.ortalama_sure
        yeni = replace(ist, ort=ist.ort + kayma, mtbf=mtbf, mttr=mttr, kapasite=kap, tampon=tampon,
                       ucgen=tuple(max(0.05, u + kayma) for u in ist.ucgen) if ist.ucgen else None)
        istasyonlar.append(yeni)

p = replace(taban, istasyonlar=tuple(istasyonlar), sure=float(sure), isinma=float(isinma), ariza=ariza)
ozel = p != replace(taban, sure=float(sure), isinma=float(isinma), ariza=ariza)

# ---------------------------------------------------------------- koşu
st.title("Seri Üretim Hattı Simülasyonu")
etiket = f"{hazir} (düzenlendi)" if ozel else f"{hazir}: {SENARYOLAR[hazir][0]}"
t0 = time.perf_counter()
with st.spinner(f"{n} replikasyon koşuluyor..."):
    df = _replikasyon(p, n, seed)
o = ozetle(df)
sure_sn = time.perf_counter() - t0
st.caption(f"{etiket} · {n} replikasyon · {sure:,} dk ölçüm + {isinma} dk ısınma · "
           + ("önbellekten" if sure_sn < 0.05 else f"hesap {sure_sn:.1f} sn")
           + " · aralıklar %95 güven aralığı")

# 1) Özet kartları
c1, c2, c3, c4 = st.columns(4)
c1.metric("Verim (ürün/saat)", f"{o['verim']:.2f} ± {o['verim_yg']:.2f}")
c2.metric("Çevrim süresi (dk)", f"{o['cevrim_suresi']:.1f} ± {o['cevrim_suresi_yg']:.1f}")
c3.metric("Ortalama WIP", f"{o['wip']:.2f} ± {o['wip_yg']:.2f}")
c4.metric("Darboğaz", o["darbogaz"])
c4.caption(f"Replikasyonların %{100 * o['darbogaz_payi']:.0f}'inde en yüksek kullanım")

# 2) Kullanım grafiği
st.subheader("İstasyon durumları")
durum_ad = {"calisma": "Çalışma", "ariza": "Arıza", "bloklu": "Bloklu", "bos": "Boşta"}
satirlar = []
for c in df.columns:
    d, _, ist = c.partition(":")
    if d in durum_ad:
        satirlar.append({"İstasyon": ist, "Durum": durum_ad[d], "Pay": df[c].mean(),
                         "Darboğaz": ist == o["darbogaz"]})
dd = pd.DataFrame(satirlar)
grafik = alt.Chart(dd).mark_bar().encode(
    x=alt.X("İstasyon:N", sort=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y("Pay:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
    color=alt.Color("Durum:N", sort=list(durum_ad.values()),
                    scale=alt.Scale(domain=list(durum_ad.values()),
                                    range=["#2da44e", "#d1242f", "#bf8700", "#8c959f"])),
    order=alt.Order("sira:Q"),
    opacity=alt.condition("datum['Darboğaz']", alt.value(1.0), alt.value(0.55)),
    tooltip=["İstasyon", "Durum", alt.Tooltip("Pay:Q", format=".1%")],
).transform_calculate(sira="indexof(['Çalışma','Arıza','Bloklu','Boşta'], datum.Durum)")
st.altair_chart(grafik, width="stretch")
st.caption("Darboğaz istasyon tam renkte gösterilir; diğerleri soluk.")

# 3) Ara stok doluluğu
st.subheader("Ara stok doluluğu (ilk replikasyon, 100 dk hareketli ortalama)")
seri, tampon_tab = _ornek_kosu(p, seed)
tampon_kol = [c for c in seri.columns if c.startswith("tampon_")]
seri = seri.copy()
seri[tampon_kol] = seri[tampon_kol].rolling(10, min_periods=1).mean()
uzun = seri.melt(id_vars="t", value_vars=tampon_kol, var_name="Ara stok", value_name="Seviye")
uzun["Ara stok"] = uzun["Ara stok"].str.replace("tampon_", "Ara stok ")
st.altair_chart(alt.Chart(uzun).mark_line().encode(
    x=alt.X("t:Q", title="zaman (dk)"), y="Seviye:Q", color="Ara stok:N"),
    width="stretch")
st.dataframe(tampon_tab.round(2), hide_index=True)

# 4) Senaryo karşılaştırması
st.subheader("Senaryo karşılaştırması")
secilen = st.multiselect("Karşılaştırılacak hazır senaryolar", list(SENARYOLAR),
                         default=["S0", "S1", "S2", "S3"])
if ozel:
    st.caption("Düzenlenmiş parametreler 'Özel' satırı olarak eklenir.")
if st.button("Karşılaştırmayı koş / güncelle", type="primary"):
    st.session_state["karsilastirma"] = True
if not st.session_state.get("karsilastirma"):
    st.info("Seçilen senaryoları aynı tohumlarla koşmak için düğmeye basın. İstasyon ayarlarını "
            "değiştirdiğinizde karşılaştırma önbellekten anında gelir; yalnızca replikasyon sayısı, "
            "koşu uzunluğu veya tohum değişirse senaryolar yeniden koşulur.")
    secilen = []
ilerleme = st.progress(0.0, text="Senaryolar koşuluyor")
sonuclar = {}
toplam = len(secilen) + int(ozel)
for j, k in enumerate(secilen):
    q = replace(senaryo_param(k), sure=float(sure), isinma=float(isinma), ariza=ariza)
    sonuclar[k] = _replikasyon(q, n, seed)
    ilerleme.progress((j + 1) / max(toplam, 1), text=f"{k} tamam")
if ozel and secilen:
    sonuclar["Özel"] = df
ilerleme.empty()
if sonuclar:
    referans = "S0" if "S0" in sonuclar else next(iter(sonuclar))
    tablo = karsilastir(sonuclar, referans=referans)
    st.dataframe(tablo, hide_index=True, width="stretch")
    st.caption(f"Δ sütunları {referans} senaryosuna göre eşleştirilmiş farktır (ortak rastgele sayılar); "
               "köşeli parantez %95 güven aralığı. Aralık sıfırı içeriyorsa fark anlamsızdır.")
    vg = pd.DataFrame([{"Senaryo": k, "Verim": guven_araligi(v["verim"])[0],
                        "YG": guven_araligi(v["verim"])[1]} for k, v in sonuclar.items()])
    taban_g = alt.Chart(vg).encode(x=alt.X("Senaryo:N", sort=None))
    st.altair_chart(taban_g.mark_bar(color="#1f6feb").encode(y=alt.Y("Verim:Q", title="verim (ürün/saat)"))
                    + taban_g.mark_errorbar().encode(y="ymin:Q", y2="ymax:Q").transform_calculate(
                        ymin="datum.Verim - datum.YG", ymax="datum.Verim + datum.YG"),
                    width="stretch")

    # 5) Dışa aktarma
    hepsi = pd.concat([v.assign(senaryo=k) for k, v in sonuclar.items()], ignore_index=True)
    st.download_button("Replikasyon sonuçlarını CSV indir", hepsi.to_csv(index=False).encode("utf-8-sig"),
                       "senaryo_sonuclari.csv", "text/csv")
    st.download_button("Karşılaştırma tablosunu CSV indir", tablo.to_csv(index=False).encode("utf-8-sig"),
                       "karsilastirma.csv", "text/csv")
