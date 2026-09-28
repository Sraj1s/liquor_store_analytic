from pathlib import Path

from streamlit.testing.v1 import AppTest

from liquor.db import get_engine
from liquor.generate import generate
from liquor.pipeline import ingest
from liquor.schema import initialize


def test_dashboard_default_filters_and_empty_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LIQUOR_DEMO", "1")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "dashboard.db"))
    engine = get_engine(demo=True)
    initialize(engine)
    generate(tmp_path / "raw", days=8)
    ingest(engine, tmp_path / "raw")
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dashboard/app.py"), default_timeout=30
    ).run()
    assert not app.exception
    assert len(app.metric) == 7
    assert len(app.get("plotly_chart")) == 5
    app.sidebar.multiselect[0].set_value(["Whiskey"]).run()
    assert not app.exception
    assert len(app.metric) == 7
    app.sidebar.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any("No sales match" in element.value for element in app.info)
    engine.dispose()
