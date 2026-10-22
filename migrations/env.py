from alembic import context

from src.db.session import Base, build_engine
from src.db.settings import DatabaseSettings
from src.models.paper import Paper  # noqa: F401 -- registers model metadata

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=DatabaseSettings().sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine()
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
