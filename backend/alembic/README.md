# Alembic migrations

Database migrations belong in this directory. The initial migration creates
the schema from SQLAlchemy models. SQLite is the local default; PostgreSQL is
supported for deployments needing concurrent writers and multiple API
instances. The integration suite continues to use a disposable SQLite database.
Run migrations with `alembic upgrade head` after configuring the destination
`DATABASE_URL`.
