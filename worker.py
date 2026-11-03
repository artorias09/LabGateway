"""Single-process Docker runner. Untrusted code is never executed directly on host."""
import argparse
import sys
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import store

IMAGE = "python:3.12-alpine"
TIMEOUT_SECONDS = 15
OUTPUT_LIMIT = 12_000
DOCKER_COMMAND_TIMEOUT = 8


def _cleanup_container(name):
    """Force-remove timed-out containers; confirm that removal succeeded."""
    try:
        subprocess.run(
            ["docker", "rm", "-f", name], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=DOCKER_COMMAND_TIMEOUT, check=False,
        )
        check = subprocess.run(
            ["docker", "inspect", name], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=DOCKER_COMMAND_TIMEOUT, check=False,
        )
        return check.returncode != 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_container(path: str) -> tuple[str, str]:
    if not shutil.which("docker"):
        return "error", "Docker indisponível; execução NÃO realizada."
    source = Path(path).resolve()
    if source.parent != store.UPLOAD.resolve() or not source.is_dir():
        return "error", "Caminho de submissão recusado."
    if (source / "main.py").is_symlink() or not (source / "main.py").is_file():
        return "error", "Projeto inválido: main.py ausente ou link simbólico."
    name = "labgateway-" + uuid.uuid4().hex
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--ipc", "none",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.5",
        "--pids-limit", "32", "--user", "65534:65534",
        "--ulimit", "nofile=64:64",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--mount", f"type=bind,src={source},dst=/submission,readonly",
        "--workdir", "/submission", "--pull", "never", IMAGE,
        "python", "-B", "-I", "main.py",
    ]
    # Redirect child output to disk-backed temporary file, avoiding unbounded RAM.
    try:
        with tempfile.TemporaryFile() as capture:
            try:
                result = subprocess.run(
                    cmd, stdin=subprocess.DEVNULL, stdout=capture,
                    stderr=subprocess.STDOUT, timeout=TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                if not _cleanup_container(name):
                    return "error", "ALERTA: não foi possível confirmar remoção do contêiner. Suspenda novas execuções e verifique Docker."
                return "timeout", "Limite de execução excedido; contêiner removido."
            capture.seek(0)
            raw = capture.read(OUTPUT_LIMIT + 1)
            output = raw[:OUTPUT_LIMIT].decode("utf-8", "replace")
            if len(raw) > OUTPUT_LIMIT:
                output += "\n[saída truncada]"
            return ("passed" if result.returncode == 0 else "failed"), output
    except Exception as exc:
        if not _cleanup_container(name):
            return "error", "ALERTA: falha inesperada e estado do contêiner desconhecido. Verifique Docker."
        return "error", f"Falha no executor: {type(exc).__name__}"


def once():
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT r.id,s.path FROM runs r JOIN submissions s ON s.id=r.submission_id "
            "WHERE r.status='queued' ORDER BY r.id LIMIT 1"
        ).fetchone()
        if row:
            db.execute(
                "UPDATE runs SET status='running',started_at=? WHERE id=?",
                (store.now(), row["id"]),
            )
    if not row:
        return False
    status, output = run_container(row["path"])
    with store.connect() as db:
        db.execute(
            "UPDATE runs SET status=?,output=?,finished_at=? WHERE id=?",
            (status, output, store.now(), row["id"]),
        )
    if status == "error" and output.startswith("ALERTA:"):
        print(output, file=sys.stderr)
        sys.exit(78)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store.init()
    with store.connect() as db:
        db.execute(
            "UPDATE runs SET status='error',output='Execução interrompida pelo reinício do worker.',finished_at=? "
            "WHERE status='running'",
            (store.now(),),
        )
    # Run exactly one worker process. Do not launch additional copies.
    while True:
        if not once():
            if args.once:
                break
            time.sleep(2)
        elif args.once:
            break


if __name__ == "__main__":
    main()
