from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))


class Code(Base):
    __tablename__ = "authorization_codes"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    redirect_uri: Mapped[str] = mapped_column(String(512))
    scope: Mapped[str] = mapped_column(String(256))
    user_id: Mapped[str] = mapped_column(String(64))
    challenge: Mapped[str] = mapped_column(String(43))
    nonce: Mapped[str | None] = mapped_column(String(256), nullable=True)
    auth_time: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    service: Mapped[str] = mapped_column(String(16))
    data: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def database(url):
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
    if engine.dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL is required: SQLite cannot verify the locking guarantees")
    return engine, sessionmaker(engine, expire_on_commit=False)
