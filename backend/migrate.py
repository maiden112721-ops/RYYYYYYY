from os import environ
from pathlib import Path

from psycopg import connect


migration = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"
with connect(environ["DATABASE_URL"]) as connection:
    connection.execute(migration.read_text(encoding="utf-8"))
