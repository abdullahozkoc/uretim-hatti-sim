"""Deney katmanı, analiz ve kalibrasyon testleri."""
import numpy as np
import pytest

from src.analiz import eslestirilmis_fark, guven_araligi, hareketli_ortalama
from src.deney import (SENARYOLAR, gerekli_replikasyon, karsilastir, replikasyon,
                       senaryo_param, welch)
from src.hat import kos, temel_hat
from src.kalibrasyon import dagilim_uydur, istasyon_param_olustur, mtbf_mttr


def test_guven_araligi_bilinen_deger():
    ort, yg = guven_araligi([1, 2, 3, 4, 5])
    assert ort == 3
    assert yg == pytest.approx(2.776 * np.sqrt(2.5) / np.sqrt(5), rel=1e-3)


def test_eslestirilmis_fark():
    x = np.array([10.0, 11, 12, 13])
    f = eslestirilmis_fark(x, x + 1 + np.array([0.01, -0.01, 0.02, -0.02]))
    assert f["fark"] == pytest.approx(1.0)
    assert f["anlamli"]
    assert not eslestirilmis_fark(x, x + np.array([0.1, -0.1, 0.1, -0.1]))["anlamli"]


def test_hareketli_ortalama_sabit_seri():
    assert np.allclose(hareketli_ortalama(np.full(50, 2.0), 5), 2.0)


def test_senaryolar_parametreleri():
    s = {k: senaryo_param(k) for k in SENARYOLAR}
    assert s["S1"].istasyonlar[2].kapasite == 2
    assert all(i.tampon == 10 for i in s["S2"].istasyonlar)
    assert s["S3"].istasyonlar[2].ortalama_sure < temel_hat().istasyonlar[2].ortalama_sure
    assert s["S4"].istasyonlar[2].mtbf == 300
    assert s["S0"] == temel_hat()


def test_replikasyon_tekrarlanabilir_ve_crn():
    a = replikasyon(temel_hat(), 4)
    b = replikasyon(temel_hat(), 4)
    assert a.equals(b)
    tablo = karsilastir({"S0": a, "S1": replikasyon(senaryo_param("S1"), 4)})
    assert list(tablo["Senaryo"]) == ["S0", "S1"]


def test_welch_isinma_makul():
    w = welch(temel_hat(), n=5, sure=1_500, metrik="wip", tolerans=0.1)
    assert 0 < w["onerilen_isinma"] < 500


def test_gerekli_replikasyon_hedefi_tutar():
    g = gerekli_replikasyon(temel_hat(), "verim", hedef_oran=0.03, n0=5)
    assert g["bagil_yg"] <= 0.03 and g["n"] >= 5


def test_dagilim_uydurma_dogru_aileyi_bulur():
    rng = np.random.default_rng(1)
    x = rng.normal(2.6, 0.3, 500)
    t = dagilim_uydur(x, adaylar=("normal", "ustel"))
    assert t.iloc[0]["dagilim"] == "normal"
    ist = istasyon_param_olustur("Test", x)
    assert ist.ortalama_sure == pytest.approx(2.6, abs=0.05)
    assert kos(temel_hat().istasyon_degistir(2, **{k: getattr(ist, k) for k in
               ("ort", "dagilim", "sigma", "ucgen")}), 1).ozet["verim"] > 0


def test_mtbf_mttr():
    mtbf, mttr = mtbf_mttr([100, 300, 500], [110, 320, 530])
    assert mttr == pytest.approx(20)
    assert mtbf == pytest.approx((190 + 180) / 2)
