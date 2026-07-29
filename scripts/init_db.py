"""Initialize the database schema.

This is the single official initialization path and it runs
``alembic upgrade head``. It intentionally does NOT call
``Base.metadata.create_all()``: the schema is owned by Alembic so that
development and production stay identical and migrations remain the source of
truth.

Alembic reads the database connection from the typed application settings
(``DATABASE_URL``) via ``alembic/env.py``. Requires the application environment
to be configured (see .env.example).

The migration is run through the ``alembic`` console script (rather than
importing alembic in-process) because the project's local ``alembic/`` migration
directory would otherwise shadow the installed ``alembic`` package.
"""
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    alembic_bin = shutil.which("alembic")
    if alembic_bin is None:
        raise SystemExit(
            "The 'alembic' executable was not found. "
            "Install dependencies first: pip install -r requirements.txt"
        )

    subprocess.run(
        [alembic_bin, "upgrade", "head"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    print("Database schema initialized (alembic upgrade head).")


if __name__ == "__main__":
    main()
