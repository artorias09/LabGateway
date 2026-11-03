"""Separate single-concurrency runner. Requires Docker. Never executes student code on the host."""
import argparse
import subprocess
import time
import shutil
from pathlib import Path
import store

IMAGE = 'python:3.12-alpine'
TIMEOUT_SECONDS = 15
OUTPUT_LIMIT = 12_000

def run_container(path: str) -> tuple[str,str]:
    if not shutil.which('docker'):
        return 'error','Docker indisponível; execução NÃO realizada.'
    source=Path(path).resolve()
    if source.parent != store.UPLOAD.resolve() or not source.is_dir():
        return 'error','Caminho de submissão recusado.'
    cmd=['docker','run','--rm','--network','none','--read-only',
         '--cap-drop','ALL','--security-opt','no-new-privileges',
         '--memory','128m','--memory-swap','128m','--cpus','0.5',
         '--pids-limit','32','--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=16m',
         '--mount',f'type=bind,src={source},dst=/submission,readonly',
         '--workdir','/submission','--pull','never', IMAGE,
         'python','-B','-I','main.py']
    try:
        result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,timeout=TIMEOUT_SECONDS+8,check=False)
        output=result.stdout[:OUTPUT_LIMIT].decode('utf-8','replace')
        if len(result.stdout)>OUTPUT_LIMIT: output+='\n[saída truncada]'
        return ('passed' if result.returncode==0 else 'failed'),output
    except subprocess.TimeoutExpired:
        return 'timeout','Tempo máximo excedido; execução interrompida.'
    except Exception as exc:
        return 'error',f'Falha do executor: {type(exc).__name__}'

def once():
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT r.id,s.path FROM runs r JOIN submissions s ON s.id=r.submission_id WHERE r.status='queued' ORDER BY r.id LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE runs SET status='running',started_at=? WHERE id=?",(store.now(),row['id']))
    if not row:
        return False
    status, output=run_container(row['path'])
    with store.connect() as db:
        db.execute('UPDATE runs SET status=?,output=?,finished_at=? WHERE id=?',
                   (status,output,store.now(),row['id']))
    return True

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    store.init()
    with store.connect() as db:
        db.execute("UPDATE runs SET status='error',output='Execução interrompida pelo reinício do worker.',finished_at=? WHERE status='running'",(store.now(),))
    while True:
        if not once():
            if args.once: break
            time.sleep(2)
        elif args.once: break

if __name__=='__main__':
    main()
