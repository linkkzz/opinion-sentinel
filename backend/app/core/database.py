from collections.abc import Generator

from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


database_url = settings.database_url or URL.create(
    "mysql+pymysql",
    username=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
    query={"charset": "utf8mb4"},
)
is_sqlite = str(database_url).startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def apply_lightweight_migrations() -> None:
    """为比赛阶段的小规模部署补充新增列，避免每次改字段都要求重建数据库。"""
    inspector = inspect(engine)
    if "source_items" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("source_items")}
    additions = {
        "like_count": "INTEGER NOT NULL DEFAULT 0",
        "comment_count": "INTEGER NOT NULL DEFAULT 0",
        "share_count": "INTEGER NOT NULL DEFAULT 0",
        "view_count": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE source_items ADD COLUMN {name} {definition}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
