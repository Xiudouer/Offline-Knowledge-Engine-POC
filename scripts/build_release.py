"""Whitelist release builder. Never copy private-state, Docker volumes or user HOME."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ("README.md", "PREPARE-OFFLINE.md", "UPSTREAM.md", "THIRD-PARTY.md", "LICENSE", "TEST-RESULTS.md",
         "RELEASE-INFO.json", "SOURCE-ARTIFACTS.json", "requirements.txt", "Dockerfile", ".dockerignore", ".gitignore",
         "run.py", "start.bat", "stop.bat", "demo.bat", "check.bat", "start.sh", "build-windows.ps1")
DIRECTORIES = {"offlineknowledge": {".py", ".html", ".js", ".css"}, "tests": {".py"},
               "scripts": {".py"}, "examples": {".md", ".txt"}, "licenses": None, "wheels": {".whl", ".txt"}}


def digest(file):
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(dist=None, assets=True):
    result = {name: ROOT / name for name in FILES}
    for name, suffixes in DIRECTORIES.items():
        for file in (ROOT / name).rglob("*"):
            if file.is_file() and "__pycache__" not in file.parts and (suffixes is None or file.suffix in suffixes):
                result[file.relative_to(ROOT).as_posix()] = file
    if dist:
        dist = dist.resolve()
        assert (dist / "OfflineKnowledgeEngine.exe").is_file()
        result["OfflineKnowledgeEngine.exe"] = dist / "OfflineKnowledgeEngine.exe"
        for file in (dist / "_internal").rglob("*"):
            if file.is_file(): result[file.relative_to(dist).as_posix()] = file
    if assets:
        index = json.loads((ROOT / "assets/ASSETS.json").read_text("utf8"))
        result["assets/ASSETS.json"] = ROOT / "assets/ASSETS.json"
        for name, info in index["files"].items():
            file = (ROOT / "assets" / name).resolve()
            assert file.is_relative_to((ROOT / "assets").resolve())
            assert file.is_file() and file.stat().st_size == info["bytes"] and digest(file) == info["sha256"]
            result["assets/" + name] = file
    for name, file in result.items():
        assert file.is_file(), name
        assert "private-state" not in Path(name).parts and Path(name).name not in {"access-token.txt", "compose.json", "00-init.sql", "oke-ui-token.txt"}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    args = parser.parse_args()
    files = inventory(args.dist_dir, not args.source_only)
    manifest = {name: {"bytes": file.stat().st_size, "sha256": digest(file)} for name, file in sorted(files.items())}
    args.output.mkdir(parents=True, exist_ok=True)
    kind = "Source" if args.source_only else "Windows-x64-Offline" if args.dist_dir else "Linux-x64-Offline"
    target = args.output / f"OfflineKnowledgeEngine-1.0.0-{kind}.zip"
    checksum = Path(str(target) + ".sha256")
    if target.exists() or checksum.exists(): raise FileExistsError("Refusing to overwrite an existing release")
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for name, file in sorted(files.items()):
            archive.write(file, "OfflineKnowledgeEngine/" + name)
        archive.writestr("OfflineKnowledgeEngine/MANIFEST.sha256.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
    value = digest(target)
    checksum.write_text(value + "  " + target.name + "\n", encoding="ascii")
    print(json.dumps({"archive": target.name, "bytes": target.stat().st_size, "sha256": value, "files": len(files)}))


if __name__ == "__main__": main()
