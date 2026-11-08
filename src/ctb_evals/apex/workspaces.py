"""Build APEX-Accounting team workspaces: the shared world, the task requests, and (arm B) the scaffold."""

from __future__ import annotations

import shutil
from pathlib import Path

GROUPS = {"G1": [14, 6, 5, 4, 26], "G2": [23, 13, 17, 7, 30]}


def task_dirs(apex_root: str | Path) -> dict[int, Path]:
    tasks = Path(apex_root) / "tasks"
    return {int(d.name.split("-")[3]): d for d in tasks.iterdir() if d.is_dir()}


def request_text(task_dir: Path) -> str:
    """The user-facing request, without Harbor's front-matter."""
    ins = (task_dir / "instruction.md").read_text(encoding="utf-8")
    return ins.split("\n---\n", 1)[1].strip() if "\n---\n" in ins else ins.strip()


def build(
    apex_root: str | Path,
    world_dir: str | Path,
    task_statement: str | Path,
    out_dir: str | Path,
    scaffold: str | Path | None = None,
    groups: dict[str, list[int]] | None = None,
) -> list[Path]:
    """One workspace per (group, arm). Arm A gets no scaffold; arm B gets ``scaffold`` copied in."""
    dirs = task_dirs(apex_root)
    world = Path(world_dir)
    made = []
    for g, numbers in (groups or GROUPS).items():
        for arm in ("A", "B") if scaffold else ("A",):
            w = Path(out_dir) / f"apex_{g}_{arm}"
            if w.exists():
                shutil.rmtree(w)
            shutil.copytree(world, w / "world", ignore=shutil.ignore_patterns("_apps"))
            shutil.copytree(world / "_apps" / "quickbooks", w / "world" / "quickbooks_app")
            for n in numbers:
                td = w / "tasks" / f"T{n}"
                td.mkdir(parents=True)
                (td / "REQUEST.md").write_text(request_text(dirs[n]) + "\n", encoding="utf-8")
                fs = dirs[n] / "environment" / "task_files" / "filesystem"
                if fs.is_dir():
                    shutil.copytree(fs, td / "files")
            (w / "output").mkdir()
            shutil.copy(task_statement, w / "TASK.md")
            if arm == "B" and scaffold:
                for x in Path(scaffold).iterdir():
                    (shutil.copytree if x.is_dir() else shutil.copy)(x, w / x.name)
            made.append(w)
    return made
