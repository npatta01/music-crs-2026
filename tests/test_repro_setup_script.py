import errno
import os
import pty
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = REPO_ROOT / "scripts" / "repro_setup.sh"
HEADINGS = [
    "[1/5] Checking prerequisites",
    "[2/5] Installing Python environment",
    "[3/5] Downloading the offline reproduction bundle",
    "[4/5] Extracting cache components",
    "[5/5] Verifying bundle integrity",
]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _fake_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    fake_bin = repo / "fake-bin"
    verify_dir = repo / ".repro" / "scripts"
    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    verify_dir.mkdir(parents=True)
    shutil.copy2(SETUP_SCRIPT, scripts_dir / "repro_setup.sh")

    _write_executable(
        fake_bin / "uv",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$UV_LOG"
if [[ "${1:-}" == "--version" ]]; then
  echo "uv 0.11.29"
elif [[ "${1:-}" == "sync" ]]; then
  mkdir -p .venv/bin
  printf 'export PATH="%s/.venv/bin:$PATH"\\n' "$PWD" > .venv/bin/activate
  cat > .venv/bin/hf <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "hf 1.12.0"
fi
EOF
  /bin/chmod +x .venv/bin/hf
fi
""",
    )
    _write_executable(fake_bin / "tar", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(fake_bin / "chmod", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(verify_dir / "verify_bundle.sh", "#!/usr/bin/env bash\nexit 0\n")

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
    env["UV_LOG"] = str(repo / "uv.log")
    env.pop("NO_COLOR", None)
    return repo, env


def _run_in_pty(repo: Path, env: dict[str, str]) -> str:
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        ["bash", "scripts/repro_setup.sh"],
        cwd=repo,
        env=env,
        stdout=slave_fd,
        stderr=slave_fd,
    )
    os.close(slave_fd)
    chunks = []
    while True:
        try:
            chunk = os.read(master_fd, 4096)
        except OSError as error:
            if error.errno == errno.EIO:
                break
            raise
        if not chunk:
            break
        chunks.append(chunk)
    os.close(master_fd)
    assert process.wait(timeout=10) == 0
    return b"".join(chunks).decode()


def _assert_numbered_headings(output: str) -> None:
    positions = [output.index(heading) for heading in HEADINGS]
    assert positions == sorted(positions)


def test_plain_output_numbers_all_steps_without_ansi(tmp_path: Path) -> None:
    repo, env = _fake_repo(tmp_path)

    result = subprocess.run(
        ["bash", "scripts/repro_setup.sh"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    _assert_numbered_headings(result.stdout)
    assert "\x1b[" not in result.stdout
    assert result.stdout.index("[2/5]") < result.stdout.index("hf 1.12.0")
    uv_calls = (repo / "uv.log").read_text().splitlines()
    assert "sync" in uv_calls
    assert not any(call.startswith(("venv", "pip install")) for call in uv_calls)
    assert "scripts/repro_run.sh --eval_dataset devset" in result.stdout


def test_interactive_output_uses_ansi_styling(tmp_path: Path) -> None:
    repo, env = _fake_repo(tmp_path)

    output = _run_in_pty(repo, env)

    _assert_numbered_headings(output)
    assert "\x1b[" in output


def test_no_color_disables_ansi_in_interactive_output(tmp_path: Path) -> None:
    repo, env = _fake_repo(tmp_path)
    env["NO_COLOR"] = "1"

    output = _run_in_pty(repo, env)

    _assert_numbered_headings(output)
    assert "\x1b[" not in output
