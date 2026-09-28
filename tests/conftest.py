import pytest
from sqlalchemy import create_engine, event

from liquor.schema import initialize


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    initialize(engine)
    yield engine
    engine.dispose()
