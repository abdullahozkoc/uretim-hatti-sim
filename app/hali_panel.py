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
from src.hali.model import ETIKET, PERSONEL_SINIF, kos  # noqa: E402
from src.hali.parametre import HaliParam  # noqa: E402
from src.hali.rapor import PERSONEL_SIRA, RENK, TEZGAH_SIRA  # noqa: E402
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
n = sb.slider("Replikasyon sayısı", 3, 40, 8)
gun = sb.select_slider("Ölçüm süresi (gün)", [1, 3, 5, 7, 14], 3)
seed = int(sb.number_input("Taban rastgele tohum", 0, 10**6, 7000))

MOLA = ["toplu", "kademeli", "capraz", "yedek"]
with sb.expander("Personel ve mola", expanded=True):
    opt = st.slider("Operatör başına tezgâh", 1, 4, taban.operator_basina_tezgah)
    tlt = st.slider("Telci başına tezgâh", 1, 4, taban.telci_basina_tezgah)
    mola = st.selectbox("Mola düzeni", MOLA, MOLA.index(taban.mola_duzeni),
                        help="toplu: herkes aynı anda · kademeli: aynı roldeki komşu bakar · "
                             "capraz: aynı tezgâhın operatörü ve telcisi birbirine bakar · yedek: yüzer personel bakar")
    kural = st.selectbox("İş seçme kuralı", ["oncelikli", "fifo", "en_yakin"],
                         ["oncelikli", "fifo", "en_yakin"].index(taban.secim_kurali))
with sb.expander("Tezgâh ve kopuşlar"):
    devir_k = st.slider("Devir çarpanı (tüm tezgâhlar)", 0.7, 1.3, 1.0, 0.05,
                        help="Her tezgâhın devir dağılımını ölçekler")
    atki = st.slider("Atkı kopuşu (/dokuma saati)", 0.0, 6.0, float(round(taban.atki_kopus_saat, 2)), 0.1)
    cozgu = st.slider("Çözgü/hav kopuşu (/dokuma saati)", 0.0, 6.0, float(round(taban.cozgu_kopus_saat, 2)), 0.1)
with sb.expander("Renk değişimi ve bakım"):
    renk_ol = st.slider("Topta renk değişimi olasılığı", 0.0, 1.0, float(taban.renk_degisim_olasiligi), 0.05)
    renk_ekip = st.slider("Renk ekibi sayısı", 1, 4, taban.renk_ekibi)
    renk_pay = st.slider("Ekibin yaptığı pay", 0.0, 1.0, float(taban.renk_ekip_payi), 0.05)
    renk_k = st.slider("Renk değişimi süresi çarpanı", 0.3, 1.5, 1.0, 0.05)
    mtbf = st.slider("Arıza aralığı MTBF (dokuma saati)", 5, 200, int(taban.ariza_mtbf_saat), 5)
    tek = st.slider("Teknisyen sayısı", 1, 4, taban.teknisyen_sayisi)

p = replace(taban, operator_basina_tezgah=opt, telci_basina_tezgah=tlt, mola_duzeni=mola, secim_kurali=kural,
            tezgahlar=tuple(replace(t, devir=t.devir.olcekle(devir_k)) for t in taban.tezgahlar),
            atki_kopus_saat=atki, cozgu_kopus_saat=cozgu, renk_degisim_olasiligi=renk_ol, renk_ekibi=renk_ekip,
            renk_ekip_payi=renk_pay, renk_degisim=taban.renk_degisim.olcekle(renk_k),
            ariza_mtbf_saat=float(mtbf), teknisyen_sayisi=tek, sure_gun=float(gun))

# ------------------------------------------------------------------- koşu
st.title("Halı Dokuma Salonu Simülasyonu")
olculen = sum(1 for _, r in p.tablo().iterrows() if r["Kaynak"].startswith("ÖLÇÜM"))
st.caption(f"{hazir}: {SENARYOLAR[hazir][0]} · {p.tezgah_sayisi} tezgâh, {p.kisi_sayisi('operator')} operatör, "
           f"{p.kisi_sayisi('telci')} telci{f' + {p.yedek_sayisi} yedek' if p.mola_duzeni == 'yedek' else ''} · "
           f"{n} replikasyon × {gun} gün · %95 güven aralığı · ölçülmüş parametre: {olculen}")
if not olculen:
    st.warning("Tezgâh bilgileri fabrikadan; devir, kopuş, süreler ve olasılıklar VARSAYIM. Sayılar yöntemi "
               "gösterir; iş etüdü ölçümleriyle güncelleyin (İş etüdü sekmesi).", icon="⚠️")

with st.spinner("Simülasyon koşuluyor..."):
    df = _rep(p, n, seed)
    ornek = _tek(p, seed)

c = st.columns(5)
for col, (m, ad, f) in zip(c, (("m2_vardiya", "Salon m²/vardiya", "{:,.0f}"),
                               ("tezgah_verimi", "Tezgâh dokuma oranı", "{:.1%}"),
                               ("girisim", "Personel bekleme (girişim)", "{:.1%}"),
                               ("operator_doluluk", "Operatör doluluğu", "{:.1%}"),
                               ("telci_doluluk", "Telci doluluğu", "{:.1%}"))):
    o, yg = guven_araligi(df[m])
    col.metric(ad, f.format(o), help=f"± {f.format(yg)} (%95 GA)")

sek = st.tabs(["Durumlar", "Zaman çizelgesi", "Senaryo karşılaştırma", "Kişi başına tezgâh", "İş etüdü"])

# ---------------------------------------------------------------- durumlar
with sek[0]:
    st.subheader("Tezgâh başına m²/vardiya")
    st.altair_chart(alt.Chart(ornek.tezgah).mark_bar(color=RENK["dokuma"]).encode(
        x=alt.X("tezgah:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("m2_vardiya:Q", title="m²/vardiya"),
        tooltip=["tezgah", "marka", "tarak", alt.Tooltip("m2_vardiya:Q", format=",.1f"),
                 alt.Tooltip("ort_devir:Q", format=".1f", title="ort. devir")]).properties(height=220),
        width="stretch")
    st.subheader("Tezgâhlar")
    st.altair_chart(yigin(uzun(ornek.tezgah, "tezgah", TEZGAH_SIRA), TEZGAH_SIRA, "tezgah"), width="stretch")
    a, b = st.columns(2)
    for col, rol, ad in ((a, "operator", "Operatörler"), (b, "telci", "Telciler")):
        g = ornek.personel[ornek.personel["rol"] == rol]
        col.subheader(ad)
        col.altair_chart(yigin(uzun(g, "personel", PERSONEL_SIRA), PERSONEL_SIRA, "personel"), width="stretch")
    st.caption("İlk replikasyonun kaynak bazında dağılımı. Özet kartları tüm replikasyonların ortalamasıdır.")
    st.subheader("Personel zamanı, iş etüdü sınıflarına göre")
    satir = []
    for rol, onek in (("Operatör", "op"), ("Telci", "tl")):
        sinif = {}
        for d, s_ in PERSONEL_SINIF.items():
            sinif[s_] = sinif.get(s_, 0) + df[f"{onek}:{d}"].mean()
        satir.append({"Rol": rol, **{k: f"%{100 * v:.1f}" for k, v in sinif.items()}})
    st.dataframe(pd.DataFrame(satir), hide_index=True)
    with st.expander("Tezgâh ve personel tabloları"):
        st.dataframe(ornek.tezgah.round(3), hide_index=True)
        st.dataframe(ornek.personel.round(3), hide_index=True)

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
    sira = list(dict.fromkeys(TEZGAH_SIRA + PERSONEL_SIRA))
    kaynaklar = []
    ops = list(ornek.personel.query("rol=='operator'")["personel"])
    tls = list(ornek.personel.query("rol=='telci'")["personel"])
    for i, t in enumerate(ornek.tezgah["tezgah"]):
        kaynaklar += [t] + ([ops[i]] if i < len(ops) else []) + ([tls[i]] if i < len(tls) else [])
    kaynaklar = list(dict.fromkeys(kaynaklar + list(ornek.personel["personel"])))
    st.altair_chart(alt.Chart(cz).mark_bar().encode(
        x=alt.X("bas:Q", title="vardiya içi dakika", scale=alt.Scale(domain=[0, p.vardiya_dk])), x2="bit:Q",
        y=alt.Y("kaynak:N", sort=kaynaklar, title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.Color("Durum:N", scale=alt.Scale(domain=[ETK[d] for d in sira], range=[RENK[d] for d in sira]),
                        legend=alt.Legend(orient="bottom", columns=4, title=None, labelLimit=400, symbolLimit=0)),
        tooltip=["kaynak", "Durum", alt.Tooltip("bas:Q", format=".1f"), alt.Tooltip("bit:Q", format=".1f")],
    ).properties(height=alt.Step(22)), width="stretch")
    st.caption("Turuncu: tezgâh durmuş, operatörü ya da telciyi bekliyor. Mola saatlerinde turuncunun birikmesi "
               "mola düzeninin etkisini gösterir.")

# --------------------------------------------------------- karşılaştırma
with sek[2]:
    secilen = st.multiselect("Senaryolar", list(SENARYOLAR), default=["H0", "H1", "H2", "H4", "H6", "H9"])
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
        for onek, baslik in (("op", "Operatör zamanı"), ("tl", "Telci zamanı")):
            opd = []
            for k, v in sonuc.items():
                for d in PERSONEL_SIRA:
                    pay = v[f"{onek}:{d}"].mean() + (v[f"{onek}:kisisel"].mean() if d == "mola" else 0)
                    opd.append({"Senaryo": k, "durum": d, "pay": pay})
            st.altair_chart(yigin(pd.DataFrame(opd), PERSONEL_SIRA, "Senaryo").properties(title=baslik),
                            width="stretch")
        hepsi = pd.concat([v.assign(senaryo=k) for k, v in sonuc.items()])
        st.download_button("Replikasyon sonuçlarını CSV indir", hepsi.to_csv(index=False).encode("utf-8-sig"),
                           "hali_senaryolar.csv", "text/csv")
    else:
        st.info("Seçilen senaryolar aynı tohumlarla koşulur; farklar H0'a göre eşleştirilmiş güven aralığıyla verilir.")

# ------------------------------------------------------------ atama
with sek[3]:
    st.write("Kişi başına tezgâh sayısı arttıkça personel doluluğu artar, tezgâhların personel bekleme kaybı "
             "(makine girişimi) da artar. En iyi nokta, üretim ile işçilik maliyeti arasındaki dengedir.")
    k0, k1, k2 = st.columns(3)
    rol_sec = k0.selectbox("Rol", ["telci", "operator"])
    katki = k1.number_input("m² başına katkı payı (TL, VARSAYIM)", 0.0, 10_000.0, 60.0, 5.0)
    ucret = k2.number_input("Personel maliyeti (TL/saat, VARSAYIM)", 0.0, 10_000.0, 250.0, 10.0)
    if st.button("Eğriyi koş"):
        eg = atama_egrisi(rol_sec, (1, 2, 3, 4), n=max(3, n // 2), temel=p, katki_tl_m2=katki,
                          personel_tl_saat=ucret, paralel=False, taban_seed=seed)
        st.dataframe(eg.round(3), hide_index=True, width="stretch")
        for m, ad in (("m2_vardiya", "Salon m²/vardiya"), ("girisim", "Personel bekleme oranı"),
                      ("net_katki_vardiya", "Net katkı (TL/vardiya)")):
            st.altair_chart(alt.Chart(eg).mark_line(point=True).encode(
                x=alt.X("tezgah_kisi:O", title=f"{rol_sec} başına tezgâh"), y=alt.Y(f"{m}:Q", title=ad),
                tooltip=["tezgah_kisi", alt.Tooltip(f"{m}:Q", format=",.3f")]).properties(height=220),
                width="stretch")

# ----------------------------------------------------------- iş etüdü
with sek[4]:
    st.subheader("Tezgâhlar")
    st.dataframe(p.tezgah_tablosu(), hide_index=True, width="stretch")
    st.subheader("Parametreler ve kaynakları")
    st.dataframe(p.tablo(), hide_index=True, width="stretch")
    st.download_button("Parametreleri JSON indir", json.dumps(p.sozluk(), ensure_ascii=False, indent=2).encode(),
                       "parametreler.json", "application/json")

    st.subheader("Sanal iş örneklemesi")
    st.write("Gerçek etüde başlamadan önce: rastgele zamanlı gözlem turlarıyla durum oranlarını ne kadar "
             "doğru tahmin edersiniz? Her turda tüm tezgâhlar, operatörler ve telciler bir kez gözlenir.")
    tur = st.slider("Gözlem turu sayısı", 10, 1000, 100, 10)
    g = ie.sanal_is_ornekleme(ornek, tur, seed=seed)
    kars = ie.karsilastir(g, ie.gercek_oranlar(ornek))
    kars["durum"] = kars["durum"].map(ETIKET).fillna(kars["durum"])
    st.dataframe(kars.round(3), hide_index=True, width="stretch")
    st.caption("oran: örneklemeden tahmin · alt/üst: %95 GA (tur bazında) · gercek: simülasyondaki zaman oranı · "
               "gerekli_tur: ±3 puan hassasiyet için gereken tur sayısı")
    st.subheader("Rastgele tur planı")
    t1, t2, t3 = st.columns(3)
    plan_bas = t1.date_input("Başlangıç tarihi")
    plan_gun = t2.number_input("Gün", 1, 60, 10)
    plan_tur = t3.number_input("Vardiya başına tur", 1, 12, 3)
    plan = ie.tur_plani(str(plan_bas), int(plan_gun), int(plan_tur), seed=seed)
    st.download_button("Tur planını CSV indir", plan.to_csv(index=False).encode("utf-8-sig"), "tur_plani.csv",
                       "text/csv")

    st.subheader("Sahadan gelen formlar")
    st.write("Şablonlar: `data/hali/is_etudu/`. Bütün formları birlikte analiz etmek için: "
             "`python -m src.hali.is_etudu analiz --kayit-saat <saat>`. Burada tek tek de yükleyebilirsiniz.")
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
