"""Halı dokuma salonu paneli: operatör ve tezgâh durumları, senaryolar, iş etüdü.

Çalıştırma:  streamlit run app/hali_panel.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.analiz import guven_araligi  # noqa: E402
from src.hali import is_etudu as ie  # noqa: E402
from src.hali.model import ETIKET, OPERATOR_SINIF, kos  # noqa: E402
from src.hali.parametre import HaliParam  # noqa: E402
from src.hali.rapor import OPERATOR_SIRA, RENK, TEZGAH_SIRA  # noqa: E402
from src.hali.senaryo import SENARYOLAR, atama_egrisi, karsilastir, replikasyon, senaryo_param  # noqa: E402

st.set_page_config(page_title="Halı Dokuma Simülasyonu", layout="wide")
ETK = {**ETIKET, "mola": "Mola + kişisel"}


@st.cache_data(show_spinner=False)
def _rep(p: HaliParam, n: int, seed: int) -> pd.DataFrame:
    return replikasyon(p, n, seed, paralel=False)


@st.cache_data(show_spinner=False)
def _tek(p: HaliParam, seed: int):
    return kos(p, seed)


def yigin(df: pd.DataFrame, sira, satir: str):
    """df: satir, durum, pay sütunlu uzun tablo -> yatay yığılmış çubuk."""
    df = df.assign(Durum=df["durum"].map(ETK), sira=df["durum"].map({d: i for i, d in enumerate(sira)}))
    return alt.Chart(df).mark_bar(stroke="white", strokeWidth=1).encode(
        y=alt.Y(f"{satir}:N", sort=None, title=None),
        x=alt.X("pay:Q", stack="zero", axis=alt.Axis(format="%"), title=None, scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("Durum:N", scale=alt.Scale(domain=[ETK[d] for d in sira], range=[RENK[d] for d in sira]),
                        legend=alt.Legend(orient="bottom", columns=2, title=None, labelLimit=400, symbolLimit=0)),
        order=alt.Order("sira:Q"),
        tooltip=[satir, "Durum", alt.Tooltip("pay:Q", format=".1%")])


def uzun(df: pd.DataFrame, satir_sutunu: str, sira) -> pd.DataFrame:
    d = df.copy()
    if "kisisel" in d:
        d["mola"] = d["mola"] + d["kisisel"]
    return d.melt(id_vars=satir_sutunu, value_vars=list(sira), var_name="durum", value_name="pay")


# ------------------------------------------------------------------- kenar
sb = st.sidebar
sb.title("Parametreler")
yuklenen = sb.file_uploader("Parametre dosyası (JSON, iş etüdünden)", type="json")
temel = HaliParam.sozlukten(json.load(yuklenen)) if yuklenen else HaliParam()
hazir = sb.selectbox("Senaryo hazır ayarı", list(SENARYOLAR), format_func=lambda k: f"{k}: {SENARYOLAR[k][0]}")
taban = senaryo_param(hazir, temel)
n = sb.slider("Replikasyon sayısı", 3, 40, 10)
gun = sb.select_slider("Ölçüm süresi (gün)", [1, 3, 5, 7, 14], 5)
seed = int(sb.number_input("Taban rastgele tohum", 0, 10**6, 7000))

with sb.expander("Salon ve operatörler", expanded=True):
    tz_n = st.slider("Tezgâh sayısı", 2, 40, taban.tezgah_sayisi)
    opt = st.slider("Operatör başına tezgâh", 1, 10, taban.operator_basina_tezgah)
    mola = st.selectbox("Mola düzeni", ["toplu", "kademeli", "yedek"], ["toplu", "kademeli", "yedek"].index(taban.mola_duzeni),
                        help="toplu: herkes aynı anda, tezgâhlara kimse bakmaz · kademeli: komşu bakar · yedek: yüzer operatör bakar")
    kural = st.selectbox("İş seçme kuralı", ["fifo", "en_yakin", "oncelikli"],
                         ["fifo", "en_yakin", "oncelikli"].index(taban.secim_kurali))
    yurume = st.slider("Tezgâhlar arası yürüme (dk)", 0.0, 1.0, float(taban.yurume_tezgah_arasi), 0.05)
with sb.expander("Tezgâh ve kopuşlar"):
    devir = st.slider("Tezgâh hızı (atkı/dk)", 50, 200, int(taban.devir), 5)
    atki = st.slider("Atkı kopuşu (/dokuma saati)", 0.0, 6.0, float(round(taban.atki_kopus_saat, 2)), 0.1)
    cozgu = st.slider("Çözgü kopuşu (/dokuma saati)", 0.0, 6.0, float(round(taban.cozgu_kopus_saat, 2)), 0.1)
    ayar_k = st.slider("Ayar ve çözgü değişim süresi çarpanı", 0.3, 1.5, 1.0, 0.05)
with sb.expander("Bakım"):
    mtbf = st.slider("Arıza aralığı MTBF (dokuma saati)", 5, 200, int(taban.ariza_mtbf_saat), 5)
    tek = st.slider("Teknisyen sayısı", 1, 4, taban.teknisyen_sayisi)

p = replace(taban, tezgah_sayisi=tz_n, operator_basina_tezgah=opt, mola_duzeni=mola, secim_kurali=kural,
            yurume_tezgah_arasi=yurume, devir=float(devir), atki_kopus_saat=atki, cozgu_kopus_saat=cozgu,
            ayar=taban.ayar.olcekle(ayar_k), cozgu_degisim=taban.cozgu_degisim.olcekle(ayar_k),
            ariza_mtbf_saat=float(mtbf), teknisyen_sayisi=tek, sure_gun=float(gun))

# ------------------------------------------------------------------- koşu
st.title("Halı Dokuma Salonu Simülasyonu")
olculen = sum(1 for _, r in p.tablo().iterrows() if r["Kaynak"].startswith("ÖLÇÜM"))
st.caption(f"{hazir}: {SENARYOLAR[hazir][0]} · {p.tezgah_sayisi} tezgâh, {p.operator_sayisi} operatör"
           f"{' + yedek' if p.mola_duzeni == 'yedek' else ''} · {n} replikasyon × {gun} gün · "
           f"%95 güven aralığı · ölçülmüş parametre: {olculen}")
if not olculen:
    st.warning("Bütün parametreler VARSAYIM. Sayılar yöntemi gösterir; iş etüdü ölçümleriyle güncelleyin "
               "(İş etüdü sekmesi).", icon="⚠️")

with st.spinner("Simülasyon koşuluyor..."):
    df = _rep(p, n, seed)
    ornek = _tek(p, seed)

c = st.columns(5)
for col, (m, ad, f) in zip(c, (("m2_gun", "Üretim (m²/gün)", "{:,.0f}"), ("tezgah_verimi", "Tezgâh dokuma oranı", "{:.1%}"),
                               ("girisim", "Operatör bekleme (girişim)", "{:.1%}"),
                               ("operator_doluluk", "Operatör doluluğu", "{:.1%}"),
                               ("m2_operator_saat", "m² / operatör-saat", "{:,.1f}"))):
    o, yg = guven_araligi(df[m])
    col.metric(ad, f.format(o), help=f"± {f.format(yg)} (%95 GA)")

sek = st.tabs(["Durumlar", "Zaman çizelgesi", "Senaryo karşılaştırma", "Operatör ataması", "İş etüdü"])

# ---------------------------------------------------------------- durumlar
with sek[0]:
    a, b = st.columns(2)
    a.subheader("Tezgâhlar")
    a.altair_chart(yigin(uzun(ornek.tezgah, "tezgah", TEZGAH_SIRA), TEZGAH_SIRA, "tezgah"), width="stretch")
    b.subheader("Operatörler")
    b.altair_chart(yigin(uzun(ornek.operator, "operator", OPERATOR_SIRA), OPERATOR_SIRA, "operator"), width="stretch")
    st.caption("İlk replikasyonun kaynak bazında dağılımı. Özet kartları tüm replikasyonların ortalamasıdır.")
    sinif = {}
    for d, s in OPERATOR_SINIF.items():
        sinif[s] = sinif.get(s, 0) + df[f"op:{d}"].mean()
    st.subheader("Operatör zamanı, iş etüdü sınıflarına göre")
    st.dataframe(pd.DataFrame({"Sınıf": list(sinif), "Pay": [f"%{100 * v:.1f}" for v in sinif.values()]}),
                 hide_index=True)
    with st.expander("Tezgâh ve operatör tabloları"):
        st.dataframe(ornek.tezgah.round(3), hide_index=True)
        st.dataframe(ornek.operator.round(3), hide_index=True)

# ---------------------------------------------------------- zaman çizelgesi
with sek[1]:
    vardiya_say = int(p.sure_gun * 1440 // p.vardiya_dk)
    v = st.slider("Vardiya", 1, vardiya_say, 1)
    bas = p.isinma_dk + (v - 1) * p.vardiya_dk
    cz = ornek.cizelge
    cz = cz[(cz["bit"] > bas) & (cz["bas"] < bas + p.vardiya_dk)].copy()
    cz["bas"] = cz["bas"].clip(lower=bas) - bas
    cz["bit"] = cz["bit"].clip(upper=bas + p.vardiya_dk) - bas
    cz["durum"] = cz["durum"].replace({"kisisel": "mola"})
    cz["Durum"] = cz["durum"].map(ETK)
    sira = list(dict.fromkeys(TEZGAH_SIRA + OPERATOR_SIRA))
    kaynaklar = list(ornek.operator["operator"]) + list(ornek.tezgah["tezgah"])
    st.altair_chart(alt.Chart(cz).mark_bar().encode(
        x=alt.X("bas:Q", title="vardiya içi dakika", scale=alt.Scale(domain=[0, p.vardiya_dk])), x2="bit:Q",
        y=alt.Y("kaynak:N", sort=kaynaklar, title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.Color("Durum:N", scale=alt.Scale(domain=[ETK[d] for d in sira], range=[RENK[d] for d in sira]),
                        legend=alt.Legend(orient="bottom", columns=4, title=None, labelLimit=400, symbolLimit=0)),
        tooltip=["kaynak", "Durum", alt.Tooltip("bas:Q", format=".1f"), alt.Tooltip("bit:Q", format=".1f")],
    ).properties(height=alt.Step(22)), width="stretch")
    st.caption("Turuncu: tezgâh durmuş, operatörü bekliyor. Molada aynı grubun tezgâhlarında turuncu birikmesi, "
               "mola düzeninin etkisini gösterir.")

# --------------------------------------------------------- karşılaştırma
with sek[2]:
    secilen = st.multiselect("Senaryolar", list(SENARYOLAR), default=["H0", "H1", "H2", "H4", "H5", "H6"])
    if st.button("Karşılaştırmayı koş", type="primary"):
        st.session_state["hali_kars"] = True
    if st.session_state.get("hali_kars") and secilen:
        kodlar = ["H0"] + [k for k in secilen if k != "H0"]
        q = replace(temel, sure_gun=float(gun))
        sonuc = {k: _rep(senaryo_param(k, q), n, seed) for k in kodlar}
        st.dataframe(karsilastir(sonuc), hide_index=True, width="stretch")
        tz = pd.DataFrame([{"Senaryo": k, "durum": d, "pay": v[f"tz:{d}"].mean()} for k, v in sonuc.items()
                           for d in TEZGAH_SIRA])
        st.altair_chart(yigin(tz, TEZGAH_SIRA, "Senaryo").properties(title="Tezgâh zamanı"), width="stretch")
        opd = []
        for k, v in sonuc.items():
            for d in OPERATOR_SIRA:
                pay = v[f"op:{d}"].mean() + (v["op:kisisel"].mean() if d == "mola" else 0)
                opd.append({"Senaryo": k, "durum": d, "pay": pay})
        st.altair_chart(yigin(pd.DataFrame(opd), OPERATOR_SIRA, "Senaryo").properties(title="Operatör zamanı"),
                        width="stretch")
        hepsi = pd.concat([v.assign(senaryo=k) for k, v in sonuc.items()])
        st.download_button("Replikasyon sonuçlarını CSV indir", hepsi.to_csv(index=False).encode("utf-8-sig"),
                           "hali_senaryolar.csv", "text/csv")
    else:
        st.info("Seçilen senaryolar aynı tohumlarla koşulur; farklar H0'a göre eşleştirilmiş güven aralığıyla verilir.")

# ------------------------------------------------------------ atama
with sek[3]:
    st.write("Operatör başına tezgâh sayısı arttıkça operatör doluluğu artar, tezgâhların operatör bekleme "
             "kaybı (makine girişimi) da artar. En iyi nokta, üretim ile işçilik maliyeti arasındaki dengedir.")
    k1, k2 = st.columns(2)
    katki = k1.number_input("m² başına katkı payı (TL, VARSAYIM)", 0.0, 10_000.0, 60.0, 5.0)
    ucret = k2.number_input("Operatör maliyeti (TL/saat, VARSAYIM)", 0.0, 10_000.0, 250.0, 10.0)
    if st.button("Atama eğrisini koş"):
        eg = atama_egrisi((2, 3, 4, 5, 6, 8), n=max(3, n // 2), temel=replace(p, mola_duzeni=p.mola_duzeni),
                          katki_tl_m2=katki, operator_tl_saat=ucret, paralel=False, taban_seed=seed)
        st.dataframe(eg.round(3), hide_index=True, width="stretch")
        for m, ad in (("m2_gun", "Üretim (m²/gün)"), ("girisim", "Operatör bekleme oranı"),
                      ("net_katki_gun", "Günlük net katkı (TL)")):
            st.altair_chart(alt.Chart(eg).mark_line(point=True).encode(
                x=alt.X("tezgah_operator:O", title="operatör başına tezgâh"), y=alt.Y(f"{m}:Q", title=ad),
                tooltip=["tezgah_operator", alt.Tooltip(f"{m}:Q", format=",.3f")]).properties(height=220),
                width="stretch")

# ----------------------------------------------------------- iş etüdü
with sek[4]:
    st.subheader("Parametreler ve kaynakları")
    st.dataframe(p.tablo(), hide_index=True, width="stretch")
    st.download_button("Parametreleri JSON indir", json.dumps(p.sozluk(), ensure_ascii=False, indent=2).encode(),
                       "parametreler.json", "application/json")

    st.subheader("Sanal iş örneklemesi")
    st.write("Gerçek etüde başlamadan önce: rastgele zamanlı gözlem turlarıyla durum oranlarını ne kadar "
             "doğru tahmin edersiniz? Her turda tüm operatörler ve tezgâhlar bir kez gözlenir.")
    tur = st.slider("Gözlem turu sayısı", 10, 1000, 100, 10)
    g = ie.sanal_is_ornekleme(ornek, tur, seed=seed)
    kars = ie.karsilastir(g, ie.gercek_oranlar(ornek))
    kars["durum"] = kars["durum"].map(ETIKET).fillna(kars["durum"])
    st.dataframe(kars.round(3), hide_index=True, width="stretch")
    st.caption("oran: örneklemeden tahmin · alt/üst: %95 GA · gercek: simülasyondaki zaman oranı · "
               "gerekli_n: ±3 puan hassasiyet için gereken gözlem sayısı")

    st.subheader("Sahadan gelen formlar")
    st.write("Şablonlar: `data/hali/is_etudu/`. Zaman etüdü formu standart süreyi ve modele girecek dağılımı, "
             "iş örneklemesi formu ise sahadaki oranları verir ve bunlar modelle karşılaştırılır.")
    z = st.file_uploader("Zaman etüdü (CSV)", type="csv")
    if z:
        zt = ie.zaman_etudu_analiz(pd.read_csv(z))
        st.dataframe(zt.assign(dagilim=zt["dagilim"].astype(str)).round(3), hide_index=True, width="stretch")
        yeni = ie.parametreleri_guncelle(temel, zaman=zt)
        st.download_button("Ölçümlerle güncellenmiş parametreleri JSON indir",
                           json.dumps(yeni.sozluk(), ensure_ascii=False, indent=2).encode(), "parametreler_olcum.json",
                           "application/json")
        st.caption("Modele normal süre (performans puanıyla düzeltilmiş) girer; mola ve kişisel ihtiyaç modelde "
                   "ayrıca yer aldığı için tolerans payı eklenmez.")
    w = st.file_uploader("İş örneklemesi (CSV)", type="csv")
    if w:
        saha = pd.read_csv(w)
        st.dataframe(ie.karsilastir(saha, ie.gercek_oranlar(ornek)).round(3), hide_index=True, width="stretch")
        st.caption("Doğrulama: model oranı (gercek) sahadaki güven aralığının içinde mi? 'aralikta' sütunu.")
