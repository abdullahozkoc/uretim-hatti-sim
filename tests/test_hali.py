"""Halı dokuma salonu modeli ve iş etüdü araçları."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.hali import is_etudu as ie
from src.hali.model import OPERATOR_DURUMLARI, TEZGAH_DURUMLARI, kos
from src.hali.parametre import HaliParam, Urun, sabit, ucgen
from src.hali.senaryo import SENARYOLAR, karsilastir, replikasyon, senaryo_param

KISA = HaliParam(sure_gun=1.0)


def test_ayni_tohum_ayni_sonuc():
    assert kos(KISA, 3).ozet == kos(KISA, 3).ozet


def test_durum_oranlari_bire_toplanir():
    r = kos(KISA, 1)
    assert np.allclose(r.tezgah[list(TEZGAH_DURUMLARI)].sum(axis=1), 1)
    assert np.allclose(r.operator[list(OPERATOR_DURUMLARI)].sum(axis=1), 1)
    # Zaman çizelgesi, ölçüm penceresini her kaynak için boşluksuz kaplar
    for _, g in r.cizelge.groupby("kaynak"):
        assert g["bit"].max() - g["bas"].min() == pytest.approx(KISA.sure_gun * 1440)
        assert (g["bit"] - g["bas"]).sum() == pytest.approx(KISA.sure_gun * 1440)


def test_kesintisiz_dokuma_analitik_uretim():
    """Kopuş, arıza, besleme, top ve çözgü sonu yoksa üretim = hız × süre × en × yüz."""
    u = Urun("tek", 1.0, 2_000, en_m=4.0, top_uzunlugu=sabit(1e9))
    p = replace(KISA, urunler=(u,), atki_kopus_saat=0, cozgu_kopus_saat=0, ariza_mtbf_saat=0,
                besleme_aralik=sabit(1e9), cozgu_uzunlugu_m=1e9)
    r = kos(p, 1)
    assert r.ozet["tezgah_verimi"] == pytest.approx(1.0)
    beklenen = 100 / 2_000 * 1440 * 4.0 * 2 * p.tezgah_sayisi
    assert r.ozet["m2_gun"] == pytest.approx(beklenen, rel=1e-9)


def test_toplu_molada_mola_payi_takvime_uyar():
    r = kos(KISA, 2)
    planli = sum(s for _, s in KISA.molalar) / KISA.vardiya_dk
    assert r.ozet["op:mola"] == pytest.approx(planli, abs=0.01)


def test_daha_fazla_tezgah_daha_fazla_girisim():
    az = kos(replace(KISA, operator_basina_tezgah=3), 5).ozet
    cok = kos(replace(KISA, operator_basina_tezgah=6), 5).ozet
    assert cok["girisim"] > az["girisim"]
    assert cok["operator_doluluk"] > az["operator_doluluk"]
    assert az["operator_sayisi"] == 4 and cok["operator_sayisi"] == 2


def test_mola_duzenleri_girisimi_azaltir():
    ozet = {d: replikasyon(replace(KISA, mola_duzeni=d), 4).mean() for d in ("toplu", "kademeli", "yedek")}
    assert ozet["yedek"]["girisim"] < ozet["kademeli"]["girisim"] < ozet["toplu"]["girisim"]
    assert ozet["yedek"]["operator_sayisi"] == 4


def test_gecersiz_secenekler_reddedilir():
    with pytest.raises(ValueError):
        kos(replace(KISA, mola_duzeni="yok"), 1)
    with pytest.raises(ValueError):
        kos(replace(KISA, secim_kurali="rastgele"), 1)


def test_json_gidis_donus(tmp_path):
    p = HaliParam().olcum_ile("atki_mudahale", ucgen(0.4, 0.8, 1.6), "deneme")
    yol = tmp_path / "p.json"
    p.kaydet(yol)
    q = HaliParam.yukle(yol)
    assert q == p
    assert q.kaynak("atki_mudahale").startswith("ÖLÇÜM")
    assert q.kaynak("devir") == "VARSAYIM"


def test_senaryolar_ve_karsilastirma():
    sonuc = {k: replikasyon(senaryo_param(k, KISA), 3) for k in ("H0", "H2", "H5")}
    t = karsilastir(sonuc)
    assert list(t["Senaryo"]) == ["H0", "H2", "H5"]
    assert sonuc["H5"]["kopus_dokuma_saati"].mean() < sonuc["H0"]["kopus_dokuma_saati"].mean()
    assert set(SENARYOLAR) >= {"H0", "H1", "H4", "H10"}


# ------------------------------------------------------------------ iş etüdü
def test_standart_sure_ve_gerekli_gozlem():
    s = ie.standart_sure([1.0, 1.2, 0.8, 1.0], performans=110, tolerans=0.1)
    assert s["normal_sure"] == pytest.approx(1.1)
    assert s["standart_sure"] == pytest.approx(1.21)
    assert ie.gerekli_gozlem_ornekleme(0.5, hata=0.05) == 385
    assert ie.gerekli_gozlem_ornekleme(0.2, hata=0.05, goreli=True) == 6147


def test_sanal_is_ornekleme_gercege_yakinsar():
    r = kos(KISA, 1)
    g = ie.sanal_is_ornekleme(r, 800, seed=3)
    k = ie.karsilastir(g, ie.gercek_oranlar(r))
    assert (k["oran"] - k["gercek"]).abs().max() < 0.04
    assert k["aralikta"].mean() >= 0.75


def test_olcumler_parametreye_yazilir():
    rng = np.random.default_rng(0)
    zaman = pd.DataFrame({"eleman": "Atkı kopuşu", "model_alani": "atki_mudahale",
                          "sure_dk": rng.triangular(0.5, 0.9, 1.8, 60), "performans": 110})
    tablo = ie.zaman_etudu_analiz(zaman)
    assert tablo.loc[0, "n"] == 60
    kopus = pd.DataFrame({"tezgah": "T01", "tur": ["atki"] * 30, "durus_dk": np.arange(30) * 30.0,
                          "mudahale_bas_dk": np.arange(30) * 30.0 + 2, "bitis_dk": np.arange(30) * 30.0 + 3})
    ka = ie.kopus_analiz(kopus, dokuma_saati=15)
    assert ka.loc[0, "saat_basina"] == pytest.approx(2.0)
    assert ka.loc[0, "ort_bekleme_dk"] == pytest.approx(2.0)
    p = ie.parametreleri_guncelle(HaliParam(), zaman=tablo, kopus=ka)
    assert p.atki_kopus_saat == pytest.approx(2.0)
    assert p.kaynak("atki_kopus_saat").startswith("ÖLÇÜM")
    assert p.kaynak("atki_mudahale").startswith("ÖLÇÜM")
    assert p.kaynak("cozgu_mudahale") == "VARSAYIM"
    kos(replace(p, sure_gun=0.5), 1)       # ölçülmüş parametrelerle model koşar


def test_form_sablonlari_okunur():
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent / "data" / "hali" / "is_etudu"
    z = pd.read_csv(kok / "zaman_etudu.csv")
    assert set(z["model_alani"]) <= set(ie.SURE_ALANLARI)
    o = pd.read_csv(kok / "is_ornekleme.csv")
    assert set(o["durum"]) <= set(OPERATOR_DURUMLARI) | set(TEZGAH_DURUMLARI)
    ie.is_ornekleme_analiz(o)
