import os

from alembic import context
from sqlalchemy import create_engine

from authflow.models import Base

engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
