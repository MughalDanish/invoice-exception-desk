import os
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.db.base import Base
from app.db.models import (  # noqa: F401 - register metadata
    AuditEvent,
    Invoice,
    InvoiceReview,
    LedgerEntry,
    ValidationResult,
    Vendor,
)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata
url = os.environ.get("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5433/invoices")


def run_migrations_offline():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Tests can supply a connection scoped to an isolated PostgreSQL schema.
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
