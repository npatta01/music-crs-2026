from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_repro_setup_syncs_before_checking_project_hf_cli(tmp_path):
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "scripts" / "repro_setup.sh", scripts)

    venv_bin = project / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    _write_executable(
        venv_bin / "activate",
        f'export PATH="{venv_bin}:$PATH"\n',
    )

    trace = tmp_path / "trace.log"
    _write_executable(
        venv_bin / "hf",
        "#!/usr/bin/env bash\n"
        'echo "hf $*" >> "$TRACE"\n'
        'if [ "${1:-}" = "--version" ]; then echo "hf test"; fi\n',
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "uv",
        "#!/usr/bin/env bash\n"
        'echo "uv $*" >> "$TRACE"\n'
        'if [ "${1:-}" = "--version" ]; then echo "uv test"; fi\n',
    )
    _write_executable(
        fake_bin / "tar",
        "#!/usr/bin/env bash\n"
        'echo "tar $*" >> "$TRACE"\n',
    )

    verify_script = project / ".repro" / "scripts" / "verify_bundle.sh"
    verify_script.parent.mkdir(parents=True)
    _write_executable(
        verify_script,
        "#!/usr/bin/env bash\n"
        'echo "verify" >> "$TRACE"\n',
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["TRACE"] = str(trace)
    env.pop("MODAL_TOKEN_ID", None)
    env.pop("MODAL_TOKEN_SECRET", None)

    result = subprocess.run(
        [str(scripts / "repro_setup.sh")],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    calls = trace.read_text(encoding="utf-8").splitlines()
    assert "uv sync" in calls
    assert calls.index("uv sync") < calls.index("hf --version")
    assert any(call.startswith("hf download ") for call in calls)
    assert calls[-1] == "verify"
