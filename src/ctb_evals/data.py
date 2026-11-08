"""Fetch the two public benchmarks at pinned revisions and verify every file the evals read.

Nothing from either dataset is redistributed in this repository; ``ctb fetch`` clones them.
The FinBalance clone needs only git. The APEX clone needs git-lfs for the world archives.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from importlib import resources
from pathlib import Path
from typing import Any

from .io import sha256_file


def manifest() -> dict[str, Any]:
    with resources.files("ctb_evals").joinpath("data_manifest.json").open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _git(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, env=env)


def fetch(name: str, data_dir: str | Path) -> Path:
    """Clone ``name`` ('finbalance' or 'apex') into ``data_dir`` at its pinned revision."""
    import os

    src = manifest()[name]
    dest: Path = Path(data_dir) / str(src["dest"])
    if not dest.exists():
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
        _git("clone", "--filter=blob:none", "--no-checkout", src["repo"], str(dest), env=env)
    _git("checkout", "--quiet", src["revision"], cwd=dest, env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"))
    if src.get("lfs"):
        if shutil.which("git-lfs") is None:
            raise RuntimeError("APEX needs git-lfs: https://git-lfs.com")
        _git("lfs", "pull", "--include=worlds/**,tasks/*/tests/**,tasks/*/instruction.md", cwd=dest)
    return dest


def verify(name: str, data_dir: str | Path) -> list[str]:
    """Return the files whose checksum does not match the manifest (empty list = all good)."""
    src = manifest()[name]
    root = Path(data_dir) / src["dest"]
    bad = []
    for rel, digest in src["sha256"].items():
        p = root / rel
        if not p.exists() or sha256_file(p) != digest:
            bad.append(rel)
    return bad


def extract_apex_world(data_dir: str | Path, out_dir: str | Path) -> Path:
    """Unpack the APEX world (documents + QuickBooks export) the tasks refer to."""
    root = Path(data_dir) / manifest()["apex"]["dest"]
    world = next((root / "worlds").iterdir())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _extract(world / "filesystem.tar.gz", out)
    apps = out / "_apps"
    apps.mkdir(exist_ok=True)
    _extract(world / "apps_data.tar.gz", apps)
    return out


def _extract(archive: Path, dest: Path) -> None:
    with tarfile.open(archive) as tf:
        try:
            tf.extractall(dest, filter="data")  # refuses absolute paths, links out of dest, devices
        except TypeError:  # Python < 3.10.12 has no extraction filters: check members by hand
            root = dest.resolve()
            for m in tf.getmembers():
                if m.issym() or m.islnk() or not (root / m.name).resolve().is_relative_to(root):
                    raise RuntimeError(f"unsafe member in {archive.name}: {m.name}") from None
            tf.extractall(dest)
