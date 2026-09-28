import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL


def get_engine(demo=False):
    load_dotenv()
    if demo or os.getenv("DB_BACKEND") == "sqlite":
        path = Path(os.getenv("SQLITE_PATH", "data/demo.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(URL.create("sqlite", database=str(path)))

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        return engine
    required = ["DB_NAME", "DB_USER", "DB_PASSWORD"]
    if any(not os.getenv(key) for key in required):
        raise ValueError("Set DB_NAME, DB_USER and DB_PASSWORD in .env, or use --demo.")
    return create_engine(
        URL.create(
            "mysql+pymysql",
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.environ["DB_NAME"],
            query={"charset": "utf8mb4"},
        ),
        pool_pre_ping=True,
    )
