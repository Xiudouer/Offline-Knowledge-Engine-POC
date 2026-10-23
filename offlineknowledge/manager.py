"""Offline operator CLI. Asset acquisition is an explicit preparation operation only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys


def root_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def dump_private(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf8") as stream:
        stream.write(value)


def configuration(root, token, db_password, admin_password, port=18787):
    private = (root / "private-state").resolve()
    internal = {"offline": {}}
    project_name = "offlineknowledge-poc-" + hashlib.sha256(token.encode()).hexdigest()[:8]
    config = {"name": project_name, "services": {
        "db": {"image": "offlineknowledge/pgvector:1.0.0", "pull_policy": "never",
            "command": ["postgres", "-c", "log_statement=none", "-c", "log_parameter_max_length_on_error=0", "-c", "log_min_error_statement=panic", "-c", "log_connections=off", "-c", "log_disconnections=off"],
            "environment": {"POSTGRES_DB": "offlineknowledge", "POSTGRES_PASSWORD": admin_password},
            "volumes": ["pgdata:/var/lib/postgresql/data", str(private / "00-init.sql").replace("\\", "/")+":/docker-entrypoint-initdb.d/00-init.sql:ro"],
            "networks": internal, "dns": ["127.0.0.1"], "read_only": True,
            "tmpfs": ["/tmp:size=128m", "/var/run/postgresql:size=16m"],
            "healthcheck": {"test": ["CMD-SHELL", "pg_isready -U postgres -d offlineknowledge"], "interval": "5s", "timeout": "3s", "retries": 20},
            "security_opt": ["no-new-privileges:true"], "restart": "unless-stopped", "mem_limit": "1g",
            "logging": {"driver": "local", "options": {"max-size": "5m", "max-file": "2"}}},
        "ollama": {"image": "offlineknowledge/ollama:1.0.0", "pull_policy": "never", "user": "10001:10001",
            "environment": {"HOME": "/tmp", "OLLAMA_MODELS": "/models", "OLLAMA_HOST": "0.0.0.0:11434",
                "OLLAMA_NO_CLOUD": "1", "OLLAMA_NOPRUNE": "1", "OLLAMA_MAX_LOADED_MODELS": "1",
                "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_DEBUG": "0"},
            "volumes": [str((root / "assets/models").resolve()).replace("\\", "/")+":/models:ro"],
            "networks": internal, "dns": ["127.0.0.1"], "read_only": True,
            "tmpfs": ["/tmp:size=512m,mode=1777"], "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"], "restart": "unless-stopped", "mem_limit": "5g",
            "logging": {"driver": "local", "options": {"max-size": "5m", "max-file": "2"}}},
        "app": {"image": "offlineknowledge/app:1.0.0", "pull_policy": "never",
            "environment": {"OKE_ACCESS_TOKEN": token, "OKE_DB_PASSWORD": db_password, "OKE_PUBLIC_PORT": str(port)},
            "ports": [f"127.0.0.1:{port}:8080"], "depends_on": {"db": {"condition": "service_healthy"}, "ollama": {"condition": "service_started"}},
            "networks": internal, "dns": ["127.0.0.1"], "read_only": True,
            "tmpfs": ["/tmp:size=256m,mode=1777"], "cap_drop": ["ALL"], "pids_limit": 64,
            "security_opt": ["no-new-privileges:true"], "restart": "unless-stopped", "mem_limit": "1g",
            "logging": {"driver": "local", "options": {"max-size": "5m", "max-file": "2"}}}},
        "volumes": {"pgdata": {}}, "networks": {"offline": {"internal": True}}}
    # Explicit values prevent Docker client proxy defaults from being injected.
    proxy_environment = {name: "" for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}
    proxy_environment.update(NO_PROXY="*", no_proxy="*")
    for service in config["services"].values():
        service["environment"].update(proxy_environment)
    return config


def initialize(root):
    private = root / "private-state"
    private.mkdir(mode=0o777 if os.name == "nt" else 0o700)
    token, password, admin = [secrets.token_hex(32) for _ in range(3)]
    dump_private(private / "access-token.txt", token + "\n")
    dump_private(private / "compose.json", json.dumps(configuration(root, token, password, admin), indent=2))
    sql = ("CREATE EXTENSION IF NOT EXISTS vector;\n"
           f"CREATE ROLE oke LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE;\n"
           "CREATE SCHEMA oke AUTHORIZATION oke;\n"
           "GRANT CONNECT ON DATABASE offlineknowledge TO oke;\n")
    # Parent directory is private. The PostgreSQL container must be able to read this bind-mounted file.
    (private / "00-init.sql").write_text(sql, encoding="utf8")
    if os.name != "nt":
        (private / "00-init.sql").chmod(0o644)


def docker(*args, capture=False, timeout=None):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(["docker", *map(str, args)], capture_output=capture,
                            text=True, timeout=timeout, creationflags=flags)
    if result.returncode:
        raise RuntimeError("Docker operation failed; check Docker Desktop/Linux engine availability")
    return result.stdout.strip() if capture else None


def verify_assets(root, full=False):
    manifest = root / "assets/ASSETS.json"
    if not manifest.is_file():
        raise RuntimeError("Offline assets are not prepared; see PREPARE-OFFLINE.md")
    records = json.loads(manifest.read_text("utf8"))
    if "images.tar" not in records.get("files", {}) or set(records.get("image_ids", {})) != {
            "offlineknowledge/app:1.0.0", "offlineknowledge/pgvector:1.0.0", "offlineknowledge/ollama:1.0.0"}:
        raise RuntimeError("Offline artifact index is incomplete")
    for name, info in records["files"].items():
        file = (root / "assets" / name).resolve()
        if not file.is_relative_to((root / "assets").resolve()) or not file.is_file() or file.stat().st_size != info["bytes"]:
            raise RuntimeError("Offline artifact is missing or size is incorrect")
        if full:
            with file.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != info["sha256"]:
                    raise RuntimeError("Offline artifact hash mismatch")
    return records


def compose(root, *args):
    return docker("compose", "-f", root / "private-state/compose.json", *args)


def start(root):
    info = verify_assets(root, full=True)
    if docker("info", "--format", "{{.OSType}}", capture=True, timeout=15) != "linux":
        raise RuntimeError("A Docker Linux engine is required")
    if not (root / "private-state").exists():
        initialize(root)
    missing = False
    for tag, image_id in info["image_ids"].items():
        try:
            found = docker("image", "inspect", "--format", "{{.Id}}", tag, capture=True, timeout=15)
            missing = missing or found != image_id
        except RuntimeError:
            missing = True
    if missing:
        print("Loading verified offline images. No registry pull is used.", flush=True)
        docker("image", "load", "--input", root / "assets/images.tar")
    for tag, image_id in info["image_ids"].items():
        if docker("image", "inspect", "--format", "{{.Id}}", tag, capture=True, timeout=15) != image_id:
            raise RuntimeError("Loaded image identity mismatch")
    compose(root, "up", "-d", "--pull", "never", "--no-build")
    print("Open http://127.0.0.1:18787 and copy the token from private-state/access-token.txt")
    print("On first connection, model loading may take several minutes on CPU.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="OfflineKnowledgeEngine 1.0.0")
    parser.add_argument("command", choices=["start", "stop", "status", "verify", "init", "demo", "check"])
    args = parser.parse_args(argv)
    root = root_directory()
    try:
        if args.command == "start":
            start(root)
        elif args.command == "stop":
            compose(root, "stop")  # No volume deletion or user-data removal.
        elif args.command == "status":
            compose(root, "ps")
        elif args.command == "verify":
            info = verify_assets(root, True)
            print(json.dumps({"artifacts_verified": len(info["files"]), "image_ids": info["image_ids"]}))
        elif args.command == "init":
            initialize(root)
            print("Fresh local credentials generated. Do not redistribute private-state/.")
        elif args.command == "check":
            from .acceptance import run
            print(json.dumps(run(root), indent=2))
        else:
            from .selftest import demo
            print(json.dumps(demo(), ensure_ascii=True, indent=2))
        return 0
    except Exception as error:
        print("Operation failed: " + type(error).__name__, file=sys.stderr)
        if args.command == "start":
            print("Check Docker engine access and assets/ASSETS.json; see README.md.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
