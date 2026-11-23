#!/usr/bin/env python3
"""Initialize the public three-user Gitea instance and its configuration."""
import argparse, os, pathlib, pwd, sqlite3, subprocess, re

CREDS = {
    "alice": "Alice-Local-2026!",
    "bob": "Bob-Local-2026!",
    "carol": "Carol-Local-2026!",
}


def prepare(binary, data, host, port):
    data = pathlib.Path(data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    for d in ("repositories", "log", "tmp", "custom", "sessions", "avatars"):
        (data / d).mkdir(exist_ok=True)
    config = data / "app.ini"
    if config.exists() and (data / "baseline.ready").exists():
        current = config.read_text()
        for key, value in [
            ("HTTP_ADDR", host),
            ("HTTP_PORT", str(port)),
            ("ROOT_URL", f"http://127.0.0.1:{port}/"),
        ]:
            current = re.sub(r"(?m)^" + key + r"\s*=.*$", key + " = " + value, current)
        config.write_text(current)
        return config
    config.write_text(
        f"""APP_NAME = Gitea
RUN_USER = {pwd.getpwuid(os.getuid()).pw_name}
RUN_MODE = prod
WORK_PATH = {data}
[database]
DB_TYPE = sqlite3
PATH = {data}/gitea.db
[repository]
ROOT = {data}/repositories
DEFAULT_BRANCH = main
[server]
APP_DATA_PATH = {data}/appdata
DOMAIN = localhost
SSH_DOMAIN = localhost
HTTP_ADDR = {host}
HTTP_PORT = {port}
ROOT_URL = http://127.0.0.1:{port}/
DISABLE_SSH = true
OFFLINE_MODE = true
LFS_START_SERVER = true
[security]
INSTALL_LOCK = true
DISABLE_GIT_HOOKS = true
IMPORT_LOCAL_PATHS = false
PASSWORD_HASH_ALGO = pbkdf2$1000$50
[service]
DISABLE_REGISTRATION = false
REGISTER_EMAIL_CONFIRM = false
ENABLE_NOTIFY_MAIL = false
REQUIRE_SIGNIN_VIEW = false
ENABLE_CAPTCHA = false
DEFAULT_ALLOW_CREATE_ORGANIZATION = true
[mailer]
ENABLED = false
[migrations]
ALLOW_LOCALNETWORKS = false
[webhook]
ALLOWED_HOST_LIST = external
[session]
PROVIDER = file
PROVIDER_CONFIG = {data}/sessions
[log]
MODE = file
LEVEL = Warn
ROOT_PATH = {data}/log
[ui]
DEFAULT_THEME = gitea-light
[other]
SHOW_FOOTER_VERSION = false
"""
    )
    if not (data / "baseline.ready").exists():
        subprocess.run(
            [str(binary), "--work-path", str(data), "--config", str(config), "migrate"],
            check=True,
        )
        for user, password in CREDS.items():
            cmd = [
                str(binary),
                "--work-path",
                str(data),
                "--config",
                str(config),
                "admin",
                "user",
                "create",
                "--username",
                user,
                "--password",
                password,
                "--email",
                f"{user}@example.test",
                "--must-change-password=false",
            ]
            if user == "alice":
                cmd.append("--admin")
            subprocess.run(cmd, check=True)
        # The CLI has no full-name flag; set initial display names before server startup.
        with sqlite3.connect(data / "gitea.db") as db:
            for user in CREDS:
                db.execute(
                    "UPDATE user SET full_name=?, allow_create_organization=1 WHERE lower_name=?",
                    (user.capitalize() + " Example", user),
                )
        (data / "baseline.ready").write_text("three public users; no repositories\n")
    return config


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--binary", required=True)
    p.add_argument("--data", default=os.environ.get("DATA_DIR"))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "18135")))
    p.add_argument("--start", action="store_true")
    a = p.parse_args()
    if not a.binary or not a.data:
        p.error("--binary and --data required")
    config = prepare(a.binary, a.data, a.host, a.port)
    if a.start:
        os.execv(
            a.binary,
            [
                a.binary,
                "--work-path",
                str(pathlib.Path(a.data).resolve()),
                "--config",
                str(config),
                "web",
            ],
        )
    print(config)
