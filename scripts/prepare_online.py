"""Explicit online preparation on a staging machine with Docker. Never run on private documents.

Requires Python 3.12+ and Docker Linux engine. Runtime start never calls this script.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TAGS = {"offlineknowledge/pgvector:1.0.0": "pgvector/pgvector:pg16",
        "offlineknowledge/ollama:1.0.0": "ollama/ollama:latest"}


def run(*args, capture=False):
    result = subprocess.run(args, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else None


ASSETS.mkdir(exist_ok=False)
(ASSETS / "models").mkdir()
run("docker", "pull", "--platform", "linux/amd64", "python:3.12-slim-bookworm")
run("python", "-m", "pip", "download", "--index-url", "https://pypi.org/simple", "--only-binary=:all:",
    "--platform", "manylinux2014_x86_64", "--implementation", "cp", "--python-version", "312", "--abi", "cp312",
    "--dest", str(ROOT / "wheels"), "-r", str(ROOT / "requirements.txt"))
shutil.copyfile(ROOT / "requirements.txt", ROOT / "wheels/requirements.txt")
run("docker", "build", "--platform", "linux/amd64", "-t", "offlineknowledge/app:1.0.0", str(ROOT))
for local, upstream in TAGS.items():
    run("docker", "pull", "--platform", "linux/amd64", upstream)
    run("docker", "tag", upstream, local)
# Only this staging helper has temporary internet access; no knowledge documents are mounted.
container = "oke-model-preparation-" + os.urandom(6).hex()
run("docker", "run", "-d", "--name", container, "-e", "OLLAMA_NO_CLOUD=1",
    "-e", "OLLAMA_MODELS=/models", "-v", str((ASSETS / "models").resolve()) + ":/models", "ollama/ollama:latest", "serve")
try:
    run("docker", "exec", container, "ollama", "pull", "qwen3:0.6b")
    run("docker", "exec", container, "ollama", "pull", "qwen3-embedding:0.6b")
finally:
    run("docker", "rm", "-f", container)
tags = ["offlineknowledge/app:1.0.0", *TAGS]
image_ids = {tag: run("docker", "image", "inspect", "--format", "{{.Id}}", tag, capture=True) for tag in tags}
run("docker", "image", "save", "--output", str(ASSETS / "images.tar"), *tags)
files = {}
for file in sorted(ASSETS.rglob("*")):
    if file.is_file():
        with file.open("rb") as stream:
            files[file.relative_to(ASSETS).as_posix()] = {"bytes": file.stat().st_size,
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
(ASSETS / "ASSETS.json").write_text(json.dumps({"image_ids": image_ids, "files": files,
    "platform": "linux/amd64", "prepared_online": True}, indent=2), encoding="utf8")
print("Prepared. Transfer the original bundle plus assets/ to the offline machine. Never include private-state/.")
