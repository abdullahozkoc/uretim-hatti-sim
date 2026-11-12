"""M/M/1 modelinin teorik değerlere yakınlığı ve tekrarlanabilirliği.

Testler hızlı kalsın diye doğrulama tablosundan daha kısa koşular kullanılır;
tolerans, replikasyonlar arası standart hatadan türetilir (±4·SE).
Tam doğrulama tablosu için: python -m src.mm1_dogrulama
"""
import numpy as np
import pytest

from src.mm1 import MM1Parametre, kos, replikasyonlar, teorik


def test_teorik_degerler():
    th = teorik(0.9, 1.0)
    assert th["Wq"] == pytest.approx(9.0)
    assert th["Lq"] == pytest.approx(8.1)
    with pytest.raises(ValueError):
        teorik(1.0, 1.0)


def test_ayni_tohum_ayni_sonuc():
    p = MM1Parametre(lam=0.8, sure=5_000, isinma=500)
    assert kos(p, 42) == kos(p, 42)
    assert kos(p, 42) != kos(p, 43)


@pytest.mark.parametrize("lam,sure,isinma", [
    (0.5, 50_000, 2_500),
    (0.8, 100_000, 5_000),
    (0.9, 200_000, 10_000),
])
def test_teorik_yakinsama(lam, sure, isinma):
    n = 10
    sonuc = replikasyonlar(MM1Parametre(lam=lam, sure=sure, isinma=isinma), n=n)
    th = teorik(lam, 1.0)
    for anahtar in ("Wq", "Lq"):
        x = np.array([r[anahtar] for r in sonuc])
        se = x.std(ddof=1) / np.sqrt(n)
        assert abs(x.mean() - th[anahtar]) < 4 * se, (anahtar, x.mean(), th[anahtar], se)
        # Standart hata da makul ölçüde küçük olmalı (aksi halde test anlamsız)
        assert se / th[anahtar] < 0.05


def test_little_yasasi():
    lam = 0.8
    r = kos(MM1Parametre(lam=lam, sure=100_000, isinma=5_000), 7)
    assert r["Lq"] == pytest.approx(lam * r["Wq"], rel=0.03)
