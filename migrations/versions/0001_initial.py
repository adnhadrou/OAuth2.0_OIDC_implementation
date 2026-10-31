"""Initial explicit schema for protocol and browser state."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
    )
    op.create_table(
        "authorization_codes",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("scope", sa.String(256), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("challenge", sa.String(43), nullable=False),
        sa.Column("nonce", sa.String(256), nullable=True),
        sa.Column("auth_time", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "browser_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("service", sa.String(16), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "login_throttles",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for name in ("login_throttles", "browser_sessions", "authorization_codes", "users"):
        op.drop_table(name)
