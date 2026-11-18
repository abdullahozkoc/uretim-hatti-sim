"""Halı dokuma salonu modeli ve iş etüdü araçları."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.hali import is_etudu as ie
from src.hali.model import PERSONEL_DURUMLARI, TEZGAH_DURUMLARI, kos
from src.hali.parametre import HaliParam, fabrika_tezgahlari, sabit, ucgen
from src.hali.senaryo import SENARYOLAR, karsilastir, replikasyon, senaryo_param

KISA = HaliParam(sure_gun=1.0)


def test_fabrika_tezgahlari():
    t = fabrika_tezgahlari()
    assert len(t) == 14
    assert (t[0].marka, t[0].tarak, t[0].en_m, t[0].renk, t[0].tarak_sayisi) == ("Schönherr", 42, 5.0, 8, 2100)
    assert t[10].tarak == 70 and t[10].tarak_sayisi == 2800
    p = HaliParam()
    assert p.kisi_sayisi("operator") == 14 and p.kisi_sayisi("telci") == 14


def test_ayni_tohum_ayni_sonuc():
    assert kos(KISA, 3).ozet == kos(KISA, 3).ozet


def test_durum_oranlari_bire_toplanir():
    r = kos(KISA, 1)
    assert np.allclose(r.tezgah[list(TEZGAH_DURUMLARI)].sum(axis=1), 1)
    assert np.allclose(r.personel[list(PERSONEL_DURUMLARI)].sum(axis=1), 1)
    for _, g in r.cizelge.groupby("kaynak"):
        assert (g["bit"] - g["bas"]).sum() == pytest.approx(KISA.sure_gun * 1440)
    # vardiya üretimleri toplam üretime eşit
    assert r.vardiya_uretim["m2"].sum() == pytest.approx(r.tezgah["m2"].sum())
    assert r.vardiya_uretim["vardiya"].max() == 3


def test_kesintisiz_dokuma_analitik_uretim():
    """Kopuş, arıza, besleme, kontrol, top ve çözgü sonu yoksa üretim = hız × süre × en × yüz."""
    tz = tuple(replace(t, devir=sabit(90)) for t in fabrika_tezgahlari())
    p = replace(KISA, tezgahlar=tz, atki_kopus_saat=0, cozgu_kopus_saat=0, ariza_mtbf_saat=0,
                besleme_aralik=sabit(1e9), kontrol_aralik=sabit(1e9), cozgu_uzunlugu_m=1e9,
                top_uzunlugu=sabit(1e9))
    r = kos(p, 1)
    assert r.ozet["tezgah_verimi"] == pytest.approx(1.0)
    beklenen = sum(90 / (t.sira_10cm * 10 * p.atki_sistemi) * 480 * t.en_m * 2 for t in tz)
    assert r.ozet["m2_vardiya"] == pytest.approx(beklenen, rel=1e-9)


def test_devir_degiskendir():
    r = kos(KISA, 4)
    assert r.tezgah["ort_devir"].std() > 0
    assert r.tezgah["ort_devir"].between(70, 100).all()


def test_toplu_molada_mola_payi_takvime_uyar():
    r = kos(KISA, 2)
    planli = sum(s for _, s in KISA.molalar) / KISA.vardiya_dk
    assert r.ozet["op:mola"] == pytest.approx(planli, abs=0.01)
    assert r.ozet["tl:mola"] == pytest.approx(planli, abs=0.01)


def test_roller_isleri_ayirir():
    r = kos(KISA, 5)
    isl = r.isler
    assert set(isl[isl["tur"] == "cozgu_kopusu"]["personel_rol"]) == {"telci"}
    assert set(isl[isl["tur"] == "top_indirme"]["personel_rol"]) == {"operator"}
    assert r.ozet["tz:renk_degisimi"] > 0


def test_daha_az_telci_daha_fazla_girisim():
    az = replikasyon(replace(KISA, telci_basina_tezgah=1), 3).mean()
    cok = replikasyon(replace(KISA, telci_basina_tezgah=3), 3).mean()
    assert cok["girisim"] > az["girisim"]
    assert cok["telci_doluluk"] > az["telci_doluluk"]
    assert cok["telci_sayisi"] == 5


def test_mola_duzenleri_girisimi_azaltir():
    o = {d: replikasyon(replace(KISA, mola_duzeni=d), 3).mean() for d in ("toplu", "kademeli", "capraz", "yedek")}
    for d in ("kademeli", "capraz", "yedek"):
        assert o[d]["girisim"] < o["toplu"]["girisim"]
    assert o["yedek"]["personel_sayisi"] == 30


def test_gecersiz_secenekler_reddedilir():
    with pytest.raises(ValueError):
        kos(replace(KISA, mola_duzeni="yok"), 1)
    with pytest.raises(ValueError):
        kos(replace(KISA, secim_kurali="rastgele"), 1)


def test_json_gidis_donus(tmp_path):
    p = HaliParam().olcum_ile("atki_mudahale", ucgen(0.4, 0.8, 1.6), "deneme").tezgah_guncelle(
        "T03", devir=ucgen(60, 70, 80, kaynak="ÖLÇÜM: test"))
    yol = tmp_path / "p.json"
    p.kaydet(yol)
    q = HaliParam.yukle(yol)
    assert q == p
    assert q.kaynak("atki_mudahale").startswith("ÖLÇÜM")
    assert q.kaynak("atki_kopus_saat") == "VARSAYIM"
    assert q.tezgahlar[2].devir.kaynak == "ÖLÇÜM: test"


def test_senaryolar_ve_karsilastirma():
    sonuc = {k: replikasyon(senaryo_param(k, KISA), 3) for k in ("H0", "H4", "H9")}
    t = karsilastir(sonuc)
    assert list(t["Senaryo"]) == ["H0", "H4", "H9"]
    assert sonuc["H9"]["kopus_dokuma_saati"].mean() < sonuc["H0"]["kopus_dokuma_saati"].mean()
    assert set(SENARYOLAR) >= {"H0", "H2", "H6", "H11"}


# ------------------------------------------------------------------ iş etüdü
def test_standart_sure_ve_gerekli_gozlem():
    s = ie.standart_sure([1.0, 1.2, 0.8, 1.0], performans=110, tolerans=0.1)
    assert s["normal_sure"] == pytest.approx(1.1)
    assert s["standart_sure"] == pytest.approx(1.21)
    assert ie.gerekli_gozlem_ornekleme(0.5, hata=0.05) == 385
    assert ie.gerekli_gozlem_ornekleme(0.2, hata=0.05, goreli=True) == 6147


def test_sanal_is_ornekleme_gercege_yakinsar():
    r = kos(KISA, 1)
    g = ie.sanal_is_ornekleme(r, 600, seed=3)
    assert set(g["kaynak_tipi"]) == {"tezgah", "operator", "telci"}
    k = ie.karsilastir(g, ie.gercek_oranlar(r))
    assert (k["oran"] - k["gercek"]).abs().max() < 0.05
    assert k["aralikta"].mean() >= 0.75
    assert "gerekli_tur" in k


def test_tur_plani():
    t = ie.tur_plani("2026-12-01", 2, 4)
    assert len(t) == 2 * 3 * 4
    assert (t.groupby(["tarih", "vardiya"])["vardiya_ici_dk"].diff().dropna() > 0).all()


def test_olcumler_parametreye_yazilir():
    rng = np.random.default_rng(0)
    zaman = pd.DataFrame({"eleman": "Atkı kopuşu", "model_alani": "atki_mudahale",
                          "sure_dk": rng.triangular(0.5, 0.9, 1.8, 60), "performans": 110})
    tablo = ie.zaman_etudu_analiz(zaman)
    kopus = pd.DataFrame({"tezgah": "T01", "tur": ["atki"] * 30, "durus_dk": np.arange(30) * 30.0,
                          "mudahale_bas_dk": np.arange(30) * 30.0 + 2, "bitis_dk": np.arange(30) * 30.0 + 3})
    ka = ie.kopus_analiz(kopus, dokuma_saati=15)
    assert ka.loc[0, "saat_basina"] == pytest.approx(2.0)
    devir = pd.DataFrame({"tezgah": "T05", "devir": rng.normal(80, 4, 40)})
    renk = pd.DataFrame({"durus_dk": [0, 100], "ekip_gelis_dk": [10, 0], "bitis_dk": [90, 180],
                         "yapan": ["ekip", "operator"]})
    p = ie.parametreleri_guncelle(HaliParam(), zaman=tablo, kopus=ka, devir=ie.devir_analiz(devir),
                                  renk=ie.renk_analiz(renk))
    assert p.atki_kopus_saat == pytest.approx(2.0)
    assert p.kaynak("atki_mudahale").startswith("ÖLÇÜM")
    assert p.kaynak("cozgu_mudahale") == "VARSAYIM"
    assert p.renk_ekip_payi == 0.5
    assert p.tezgahlar[4].devir.kaynak.startswith("ÖLÇÜM")
    kos(replace(p, sure_gun=0.5), 1)


def test_ornek_saha_verisi_ve_analiz(tmp_path):
    ie.ornek_saha_verisi(tmp_path, gun=1.0)
    p, rapor = ie.analiz_et(tmp_path, kayit_saat=24, n_model=2)
    assert "Doğrulama: m²/vardiya" in rapor and "Zaman etüdü" in rapor
    assert p.kaynak("cozgu_kopus_saat").startswith("ÖLÇÜM")


def test_form_sablonlari_okunur():
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent / "data" / "hali" / "is_etudu"
    for ad in ("zaman_etudu", "is_ornekleme", "kopus_kayitlari", "ariza_kayitlari", "renk_degisimi_kayitlari",
               "devir_kayitlari", "uretim_kayitlari"):
        assert (kok / f"{ad}.csv").exists()
        assert ie.form_oku(kok / f"{ad}.csv") is None        # yalnızca ORNEK satırları var
    z = pd.read_csv(kok / "zaman_etudu.csv")
    assert set(z["model_alani"]) <= set(ie.SURE_ALANLARI)
    o = pd.read_csv(kok / "is_ornekleme.csv")
    assert set(o["durum"]) <= set(PERSONEL_DURUMLARI) | set(TEZGAH_DURUMLARI)
    assert set(o["kaynak_tipi"]) <= set(ie.KAYNAK_TIPLERI)
