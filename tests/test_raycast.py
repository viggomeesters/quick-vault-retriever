from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .test_cli import build_runtime


def test_raycast_script_invokes_cli_and_contains_required_metadata(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "project.synthetic.raycast",
                "record_type": "project",
                "title": "Raycast setup",
                "content": "Raycast setup invokes the general vault retriever.",
            }
        ],
    )
    script = Path(__file__).parents[1] / "raycast" / "query-vault.sh"
    executable = shutil.which("quick-vault")
    assert executable is not None
    environment = {
        **os.environ,
        "QUICK_VAULT_BIN": executable,
        "QUICK_VAULT_RUNTIME": os.fspath(runtime),
    }

    result = subprocess.run(
        ["/bin/bash", os.fspath(script), "raycast setup"],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "# Evidence" in result.stdout
    source = script.read_text(encoding="utf-8")
    assert "@raycast.schemaVersion 1" in source
    assert "@raycast.mode fullOutput" in source
    assert '"placeholder":"Ask your vault"' in source


def test_raycast_keeps_partial_evidence_visible(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "note.synthetic.partial",
                "record_type": "note",
                "title": "Partial",
                "content": "Alpha exists without the second term.",
            }
        ],
    )
    script = Path(__file__).parents[1] / "raycast" / "query-vault.sh"
    executable = shutil.which("quick-vault")
    assert executable is not None

    result = subprocess.run(
        ["/bin/bash", os.fspath(script), "alpha beta"],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "QUICK_VAULT_BIN": executable,
            "QUICK_VAULT_RUNTIME": os.fspath(runtime),
        },
    )

    assert result.returncode == 0
    assert "# Partial evidence" in result.stdout
