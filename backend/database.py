"""Manajemen koneksi SQLAlchemy 2.x (SQLite & PostgreSQL), model ORM, dan migrasi aman ExTra."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Engine,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.pool import NullPool, StaticPool

from backend.config import get_database_path, get_database_url


def _utc_now_str() -> str:
    """Kembalikan timestamp UTC berformat standar YYYY-MM-DD HH:MM:SS."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Base(DeclarativeBase):
    """Base declarative SQLAlchemy 2.x untuk seluruh tabel ExTra."""


class User(Base):
    """Model tabel pengguna untuk autentikasi multi-user (M3.2)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=_utc_now_str,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("length(trim(email)) > 0", name="ck_users_email_nonempty"),
        Index("idx_users_email", "email"),
    )


class Transaction(Base):
    """Model tabel header transaksi pengeluaran milik seorang pengguna."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    transaction_date: Mapped[str] = mapped_column(String(10), nullable=False)
    receipt_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=_utc_now_str,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped[User | None] = relationship(back_populates="transactions")
    items: Mapped[list["TransactionItem"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_transactions_date", "transaction_date"),
        Index("idx_transactions_user_id", "user_id"),
        Index("idx_transactions_user_date", "user_id", "transaction_date"),
    )


class TransactionItem(Base):
    """Model tabel rincian item belanja dalam sebuah transaksi."""

    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Lainnya",
        server_default=text("'Lainnya'"),
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint(
            "length(trim(item_name)) > 0",
            name="ck_transaction_items_name_nonempty",
        ),
        CheckConstraint(
            "length(trim(category)) > 0",
            name="ck_transaction_items_category_nonempty",
        ),
        CheckConstraint("price >= 0", name="ck_transaction_items_price_nonneg"),
        Index("idx_transaction_items_transaction_id", "transaction_id"),
        Index("idx_transaction_items_category", "category"),
    )


_ENGINE_CACHE: dict[str, Engine] = {}


def _ensure_db_parent_dir(resolved_path: str, is_uri: bool) -> None:
    """Pastikan direktori induk file SQLite otomatis dibuat sebelum koneksi dibuka."""
    if is_uri or not resolved_path or resolved_path == ":memory:":
        return
    parent_dir = Path(resolved_path).parent
    if str(parent_dir) not in ("", "."):
        parent_dir.mkdir(parents=True, exist_ok=True)


def _ensure_sqlite_url_parent_dir(url: str) -> None:
    """Pastikan direktori induk untuk URL sqlite:/// file lokal sudah ada."""
    if not url.startswith("sqlite:///") or url == "sqlite:///:memory:":
        return
    raw_file_part = url[len("sqlite:///") :]
    if not raw_file_part or raw_file_part.startswith("file:") or "?" in raw_file_part:
        return
    _ensure_db_parent_dir(raw_file_part, is_uri=False)


def resolve_database_url(db_path: str | Path | None = None) -> str:
    """Tentukan URL koneksi SQLAlchemy aktif (SQLite lokal atau PostgreSQL DATABASE_URL)."""
    if db_path is not None:
        raw_path = str(db_path)
        if raw_path == ":memory:":
            return "sqlite:///:memory:"
        if raw_path.startswith("sqlite://"):
            _ensure_sqlite_url_parent_dir(raw_path)
            return raw_path
        is_uri = raw_path.startswith("file:")
        _ensure_db_parent_dir(raw_path, is_uri=is_uri)
        if is_uri:
            return f"sqlite:///{raw_path}"
        return f"sqlite:///{Path(raw_path).resolve().as_posix()}"

    configured_url = get_database_url()
    if configured_url:
        _ensure_sqlite_url_parent_dir(configured_url)
        return configured_url

    raw_db_path = get_database_path()
    if raw_db_path == ":memory:":
        return "sqlite:///:memory:"
    is_uri = raw_db_path.startswith("file:")
    _ensure_db_parent_dir(raw_db_path, is_uri=is_uri)
    if is_uri:
        return f"sqlite:///{raw_db_path}"
    return f"sqlite:///{Path(raw_db_path).resolve().as_posix()}"


def _attach_sqlite_foreign_key_pragma(engine: Engine) -> None:
    """Pastikan PRAGMA foreign_keys = ON selalu dieksekusi di setiap koneksi SQLite."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()


def get_engine(db_path: str | Path | None = None) -> Engine:
    """Kembalikan SQLAlchemy Engine ter-cache sesuai URL SQLite/PostgreSQL aktif."""
    url = resolve_database_url(db_path)
    _ensure_sqlite_url_parent_dir(url)

    cached = _ENGINE_CACHE.get(url)
    if cached is not None:
        return cached

    if url == "sqlite:///:memory:":
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        _attach_sqlite_foreign_key_pragma(engine)
    elif url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        _attach_sqlite_foreign_key_pragma(engine)
    else:
        engine = create_engine(url, pool_pre_ping=True)

    _ENGINE_CACHE[url] = engine
    return engine


@contextmanager
def session_scope(db_path: str | Path | None = None) -> Iterator[Session]:
    """Context manager transaksi SQLAlchemy atomik (commit/rollback & close)."""
    engine = get_engine(db_path)
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Helper koneksi SQLite langsung dengan Row factory & PRAGMA foreign_keys = ON."""
    resolved_path = str(db_path) if db_path is not None else get_database_path()
    is_uri = resolved_path.startswith("file:")
    _ensure_db_parent_dir(resolved_path, is_uri=is_uri)
    conn = sqlite3.connect(resolved_path, uri=is_uri)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_transaction(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager koneksi SQLite langsung untuk kompatibilitas helper/test lama."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Inisialisasi tabel users, transactions, transaction_items, dan migrasi aman."""
    engine = get_engine(db_path)
    with engine.begin() as conn:
        # Buat tabel users terlebih dahulu agar foreign key pada migrasi transactions valid
        User.__table__.create(bind=conn, checkfirst=True)

        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())

        if "transactions" in existing_tables:
            tx_columns = {
                str(col["name"]) for col in inspector.get_columns("transactions")
            }
            if "receipt_image_path" not in tx_columns:
                conn.execute(
                    text("ALTER TABLE transactions ADD COLUMN receipt_image_path TEXT NULL")
                )
            if "user_id" not in tx_columns:
                conn.execute(
                    text(
                        "ALTER TABLE transactions "
                        "ADD COLUMN user_id INTEGER NULL REFERENCES users(id) ON DELETE CASCADE"
                    )
                )

        if "transaction_items" in existing_tables:
            item_columns = {
                str(col["name"]) for col in inspector.get_columns("transaction_items")
            }
            if "category" not in item_columns:
                conn.execute(
                    text(
                        "ALTER TABLE transaction_items "
                        "ADD COLUMN category TEXT NOT NULL DEFAULT 'Lainnya'"
                    )
                )

        Base.metadata.create_all(bind=conn)
