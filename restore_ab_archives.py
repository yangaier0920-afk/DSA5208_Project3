"""Verify and restore the seven saved A/B archives without running solvers."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "evidence/ab_final_2026-10-28/raw_archives_manifest.json"

def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(block)
    return value.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify archive hashes and inventory; do not extract.")
    args = parser.parse_args()
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(records) == 7, "Expected seven archived jobs"
    restored, present = [], []
    total = 0
    for record in records:
        archive_path = BASE / record["path"]
        with archive_path.open("rb") as stream:
            if digest(stream) != record["sha256"]:
                raise ValueError("Archive SHA-256 mismatch: " + record["path"])
        if archive_path.stat().st_size != record["size_bytes"]:
            raise ValueError("Archive size mismatch: " + record["path"])
        expected_root = archive_path.name.removesuffix(".tar.gz")
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            seen = set()
            for member in members:
                name = PurePosixPath(member.name)
                if (name.is_absolute() or ".." in name.parts or "\\" in member.name
                        or any(":" in part for part in name.parts)
                        or not name.parts or name.parts[0] != expected_root
                        or not (member.isdir() or member.isfile())
                        or member.name in seen):
                    raise ValueError("Unsafe or duplicate archive entry: " + member.name)
                seen.add(member.name)
            files = [member for member in members if member.isfile()]
            if len(files) != record["files"]:
                raise ValueError("Archive inventory mismatch: " + record["path"])
            total += len(files)
            if args.verify_only:
                continue
            results = (BASE / "results").resolve()
            destination = results / expected_root
            if destination.exists():
                if destination.is_symlink() or not destination.is_dir():
                    raise ValueError("Existing destination is not a plain directory: " + str(destination))
                # Existing evidence must match completely; never overwrite it.
                for member in files:
                    target = results.joinpath(*PurePosixPath(member.name).parts)
                    if (not target.resolve().is_relative_to(destination.resolve())
                            or not target.is_file() or target.is_symlink()):
                        raise ValueError("Existing evidence incomplete; refusing overwrite: " + str(target))
                    with target.open("rb") as current, archive.extractfile(member) as saved:
                        if digest(current) != digest(saved):
                            raise ValueError("Existing evidence differs; refusing overwrite: " + str(target))
                present.append(expected_root)
                continue
            for member in members:
                target = results.joinpath(*PurePosixPath(member.name).parts)
                if not target.resolve().is_relative_to(results):
                    raise ValueError("Extraction escaped results directory")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open("xb") as output:
                        for block in iter(lambda: source.read(1024 * 1024), b""):
                            output.write(block)
                    if os.name != "nt":
                        target.chmod(member.mode & 0o777)
                    with target.open("rb") as current, archive.extractfile(member) as saved:
                        if digest(current) != digest(saved):
                            raise ValueError("Extracted file differs: " + str(target))
            restored.append(expected_root)
    print(json.dumps({"status": "PASS", "archives": len(records), "files": total,
                      "verify_only": args.verify_only, "restored": restored,
                      "already_present_and_identical": present}, indent=2))

if __name__ == "__main__":
    main()
