"""Halı paneli duman testi."""
from pathlib import Path

import pytest

st_test = pytest.importorskip("streamlit.testing.v1")
PANEL = str(Path(__file__).resolve().parent.parent / "app" / "hali_panel.py")


def test_hali_paneli_acilir():
    at = st_test.AppTest.from_file(PANEL, default_timeout=180)
    at.run()
    assert not at.exception
    assert any("m²/gün" in m.label for m in at.metric)
    at.button[0].click().run()          # senaryo karşılaştırması
    assert not at.exception
    tablo = next(d.value for d in at.dataframe if "Senaryo" in d.value.columns)
    assert list(tablo["Senaryo"]) == ["H0", "H1", "H2", "H4", "H5", "H6"]
