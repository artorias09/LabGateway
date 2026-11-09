"""Single-process Docker runner. Untrusted code is never executed directly on host."""
import argparse
import sys
import shutil
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path

import store
from core import detect_project_type_from_path

PYTHON_IMAGE = "python:3.12-alpine"
CPP_IMAGE = "labgateway-cpp:1"
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
        if check.returncode == 0:
            return False
        health = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=DOCKER_COMMAND_TIMEOUT, check=False,
        )
        return health.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run_bounded(cmd):
    """Drain stdout continuously without allowing unbounded memory/disk usage."""
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    chunks = []
    total = [0]
    truncated = [False]

    def drain():
        while True:
            data = proc.stdout.read(16384)
            if not data:
                break
            if total[0] < OUTPUT_LIMIT:
                piece = data[:OUTPUT_LIMIT - total[0]]
                chunks.append(piece)
                total[0] += len(piece)
                if len(piece) < len(data):
                    truncated[0] = True
            else:
                truncated[0] = True

    thread = threading.Thread(target=drain, daemon=True, name="labgateway-output")
    thread.start()
    try:
        code = proc.wait(timeout=TIMEOUT_SECONDS)
        thread.join(timeout=3)
        return code, b"".join(chunks), truncated[0]
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        raise
    finally:
        if proc.stdout:
            proc.stdout.close()


def _docker_base(name, source, image):
    return [
        "docker", "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--ipc", "none",
        "--log-driver", "none",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.5",
        "--pids-limit", "32", "--user", "65534:65534",
        "--ulimit", "nofile=64:64",
        "--tmpfs", "/tmp:rw,exec,nosuid,size=32m",
        "--mount", f"type=bind,src={source},dst=/submission,readonly",
        "--workdir", "/submission", "--pull", "never", image,
    ]


def _source_files(source, suffixes):
    return sorted(
        p.relative_to(source).as_posix()
        for p in source.rglob("*")
        if p.is_file() and not p.is_symlink() and p.suffix.lower() in suffixes
    )


def _command_for(project_type, source):
    if project_type == "python":
        if not (source / "main.py").is_file() or (source / "main.py").is_symlink():
            return None, None, "Projeto Python inválido: main.py ausente."
        return PYTHON_IMAGE, ["python", "-B", "-I", "main.py"], None

    if project_type == "c":
        sources = _source_files(source, {".c"})
        if not sources:
            return None, None, "Projeto C sem arquivos fonte."
        quoted = " ".join(shlex.quote("/submission/" + p) for p in sources)
        command = f"gcc -std=c17 -Wall -Wextra -O0 {quoted} -o /tmp/labgateway-app && /tmp/labgateway-app"
        return CPP_IMAGE, ["sh", "-lc", command], None

    if project_type == "cpp":
        sources = _source_files(source, {".cpp", ".cc", ".cxx"})
        if not sources:
            return None, None, "Projeto C++ sem arquivos fonte."
        quoted = " ".join(shlex.quote("/submission/" + p) for p in sources)
        command = f"g++ -std=c++17 -Wall -Wextra -O0 {quoted} -o /tmp/labgateway-app && /tmp/labgateway-app"
        return CPP_IMAGE, ["sh", "-lc", command], None

    if project_type == "esp32-arduino":
        return None, None, (
            "Projeto ESP32/Arduino identificado. O código foi aceito e armazenado, "
            "mas a toolchain ESP32 ainda não está configurada neste servidor. "
            "Nenhum firmware foi gravado em hardware."
        )

    return None, None, "Tipo de projeto não reconhecido."


def run_container(path: str) -> tuple[str, str]:
    if not shutil.which("docker"):
        return "error", "Docker indisponível; execução NÃO realizada."

    source = Path(path).resolve()
    if source.parent != store.UPLOAD.resolve() or not source.is_dir():
        return "error", "Caminho de submissão recusado."

    project_type = detect_project_type_from_path(source)
    image, command, diagnostic = _command_for(project_type, source)
    if diagnostic:
        return ("failed" if project_type == "esp32-arduino" else "error"), diagnostic

    name = "labgateway-" + uuid.uuid4().hex
    cmd = _docker_base(name, source, image) + command
    try:
        code, raw, truncated = _run_bounded(cmd)
        output = raw.decode("utf-8", "replace")
        header = {
            "python": "Tipo detectado: Python\n",
            "c": "Tipo detectado: C\nCompilação e execução isoladas.\n",
            "cpp": "Tipo detectado: C++\nCompilação e execução isoladas.\n",
        }.get(project_type, "")
        output = header + output
        if truncated:
            output += "\n[saída truncada]"
        if code != 0 and output == header:
            output += f"Processo finalizado com código {code}."
        return ("passed" if code == 0 else "failed"), output
    except subprocess.TimeoutExpired:
        if not _cleanup_container(name):
            return "error", "ALERTA: não foi possível confirmar remoção do contêiner. Suspenda novas execuções e verifique Docker."
        return "timeout", "Limite de execução excedido; contêiner removido."
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
