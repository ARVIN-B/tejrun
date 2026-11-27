#!/root/energy_project/.venv/bin/python
import os
import subprocess
import sys

ROOT = "/root/energy_project"
PYTHON = f"{ROOT}/.venv/bin/python"
GUNICORN = f"{ROOT}/.venv/bin/gunicorn"

os.chdir(ROOT)

args = sys.argv[1:]
migrate_only = "--migrate-only" in args
skip_migrate = "--skip-migrate" in args

if not skip_migrate:
    subprocess.run(
        [PYTHON, "manage.py", "migrate", "--noinput"],
        cwd=ROOT,
        check=True,
    )

if migrate_only:
    sys.exit(0)

os.execv(
    GUNICORN,
    [
        GUNICORN,
        "--workers", "2",
        "--bind", "127.0.0.1:8000",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "config.wsgi:application",
    ],
)
