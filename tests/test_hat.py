"""Seri hat modeli: korunum, tekrarlanabilirlik, uç durumlar, Little ve darboğaz."""
import numpy as np
import pandas as pd
import pytest

from src.hat import HatParam, IstasyonParam, kos, temel_hat


def _sabit_hat(sureler, tampon=10_000, sure=1_000.0, isinma=0.0):
    ist = tuple(IstasyonParam(f"İ{i + 1}", t, "sabit", tampon=tampon) for i, t in enumerate(sureler))
    return HatParam(istasyonlar=ist, sure=sure, isinma=isinma, ariza=False)


def test_tek_istasyon_el_hesabi():
    # Sabit 2 dk, arıza yok: 1000 dk'da t=2,4,...,998 anlarında 499 çıkış
    # (t=1000'deki bitiş koşu sınırında işlenmez).
    r = kos(_sabit_hat([2.0]), 1)
    assert r.ozet["cikan"] == 499
    assert r.istasyon.loc[0, "calisma"] == pytest.approx(1.0)


def test_sabit_seri_hat_darbogaz_hizi():
    # Arıza yok, sonsuz ara stok: hat hızı en yavaş istasyonun hızıdır.
    r = kos(_sabit_hat([1.0, 3.0, 2.0], sure=3_000.0, isinma=300.0), 1)
    assert r.ozet["verim"] == pytest.approx(20.0, abs=0.05)   # 60/3
    assert r.ozet["darbogaz"] == "İ2"
    assert r.istasyon.loc[1, "calisma"] == pytest.approx(1.0)
    assert r.istasyon.loc[2, "calisma"] == pytest.approx(2 / 3, abs=1e-3)


def test_tampon_1_bloklanma():
    # Hızlı istasyon önce, yavaş sonra, tampon 1: ilk istasyon bloklanmalı.
    r = kos(_sabit_hat([1.0, 2.0], tampon=1, sure=2_000.0, isinma=100.0), 1)
    assert r.istasyon.loc[0, "bloklu"] == pytest.approx(0.5, abs=0.01)
    assert r.tampon.loc[0, "maksimum"] == 1


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_korunum(seed):
    r = kos(temel_hat(), seed)
    o = r.ozet
    assert o["giren"] == o["cikan"] + o["sistemde"]


def test_tekrarlanabilirlik():
    a, b = kos(temel_hat(), 7), kos(temel_hat(), 7)
    assert a.ozet == b.ozet
    pd.testing.assert_frame_equal(a.istasyon, b.istasyon)
    pd.testing.assert_frame_equal(a.zaman_serisi, b.zaman_serisi)
    assert kos(temel_hat(), 8).ozet != a.ozet


def test_durum_oranlari_toplami_bir():
    r = kos(temel_hat(), 3)
    toplam = r.istasyon[["calisma", "bos", "bloklu", "ariza"]].sum(axis=1)
    assert np.allclose(toplam, 1.0)
    assert r.istasyon.loc[0, "bos"] == pytest.approx(0.0)   # ilk istasyon aç kalmaz


def test_little_yasasi():
    for seed in range(5):
        assert abs(kos(temel_hat(), seed).ozet["little_farki"]) < 0.03


def test_darbogaz_istasyon_3():
    darbogazlar = [kos(temel_hat(), s).ozet["darbogaz"] for s in range(10)]
    assert all(d == "İstasyon 3" for d in darbogazlar)


def test_kapasite_2_verimi_artirir():
    s0 = np.mean([kos(temel_hat(), s).ozet["verim"] for s in range(5)])
    s1 = np.mean([kos(temel_hat().istasyon_degistir(2, kapasite=2), s).ozet["verim"] for s in range(5)])
    assert s1 > s0


def test_olay_gunlugu_mantigi():
    p = HatParam(istasyonlar=temel_hat().istasyonlar, sure=300, isinma=0, gunluk=True)
    g = kos(p, 1).gunluk
    assert g is not None and len(g) > 0
    assert g["t"].is_monotonic_increasing
    # Her parça bir istasyonda başlamadan bitemez
    b = g[g.olay == "bitis"].groupby(["kaynak", "parca"]).t.min()
    s = g[g.olay == "baslangic"].groupby(["kaynak", "parca"]).t.min()
    assert (s.loc[b.index] <= b).all()
    # Her istasyonda parçalar sırayla (FIFO) işlenir
    for k, grp in g[(g.olay == "baslangic")].groupby("kaynak"):
        assert grp["parca"].is_monotonic_increasing
