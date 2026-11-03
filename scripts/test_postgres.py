"""Run tests on an isolated PostgreSQL cluster, without existing server credentials.

Usage: python scripts/test_postgres.py
Set PG_BIN if PostgreSQL binaries are installed elsewhere. The test cluster uses
127.0.0.1:55439, a random password, and only writes under storage/pg-tests/.
It is stopped in finally. Retained files are ignored by Git.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def main():
    pg_bin = Path(os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))
    extension = ".exe" if os.name == "nt" else ""
    initdb = pg_bin / ("initdb" + extension)
    pg_ctl = pg_bin / ("pg_ctl" + extension)
    if not initdb.is_file():
        print("Set PG_BIN to a PostgreSQL bin directory, or set TEST_DATABASE_URL and run pytest.")
        return 1
    work = ROOT / "storage" / "pg-tests" / uuid4().hex
    work.mkdir(parents=True)
    password = secrets.token_hex(24)
    password_file = work / "password.txt"
    password_file.write_text(password, encoding="utf-8")
    data = work / "data"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (work / "init.log").open("w") as output:
        subprocess.run([str(initdb), "-D", str(data), "-U", "checker_tests", "--pwfile", str(password_file), "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C"], check=True, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=60, creationflags=flags)
    password_file.unlink()
    started = False
    try:
        # Do not capture pipes: on Windows a detached postgres process can inherit
        # a pipe handle and prevent communicate() from observing EOF indefinitely.
        with (work / "control.log").open("w") as output:
            process = subprocess.run([str(pg_ctl), "-D", str(data), "-l", str(work / "server.log"), "-o", "-h 127.0.0.1 -p 55439", "-w", "start"], stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=40, creationflags=flags)
        if process.returncode:
            print("Test PostgreSQL failed to start. See", work / "control.log")
            return process.returncode
        started = True
        env = os.environ.copy()
        env["TEST_DATABASE_URL"] = f"postgresql+psycopg://checker_tests:{password}@127.0.0.1:55439/postgres"
        env["PYTHONUTF8"] = "1"
        print("Running tests against isolated PostgreSQL on 127.0.0.1:55439", flush=True)
        return subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "--basetemp", str(work / "pytest")], cwd=ROOT, env=env).returncode
    finally:
        if started:
            with (work / "control.log").open("a") as output:
                subprocess.run([str(pg_ctl), "-D", str(data), "-m", "fast", "-w", "stop"], check=True, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=40, creationflags=flags)


if __name__ == "__main__":
    raise SystemExit(main())
