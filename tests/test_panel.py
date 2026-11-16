"""Panel duman testi: hatasız açılıyor ve 10 sn altında güncelleniyor."""
import time
from pathlib import Path

import pytest

st_test = pytest.importorskip("streamlit.testing.v1")
PANEL = str(Path(__file__).resolve().parent.parent / "app" / "panel.py")


def test_panel_acilir_ve_hizli_gunceller():
    at = st_test.AppTest.from_file(PANEL, default_timeout=120)
    at.run()
    assert not at.exception
    assert any("Verim" in m.label for m in at.metric)
    # Parametre değişikliği (önbellekte olmayan yeni tohum) 10 sn altında
    t0 = time.perf_counter()
    at.sidebar.number_input[1].set_value(777).run()
    assert not at.exception
    assert time.perf_counter() - t0 < 10
    # Karşılaştırma düğmesi S0-S3 tablosunu tek ekranda üretir
    at.button[0].click().run()
    assert not at.exception
    assert list(at.dataframe[1].value["Senaryo"]) == ["S0", "S1", "S2", "S3"]
    assert list(at.dataframe[2].value["Senaryo"]) == ["S1", "S3", "S2"]
