#!/usr/bin/env bash
# Test the real Docker runner using temporary harmless programs.
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Use sudo para executar smoke_pi.sh"; exit 2; }
[ -x /opt/labgateway/.venv/bin/python ] || { echo "LabGateway ainda nao instalado"; exit 2; }
cd /opt/labgateway
docker image inspect python:3.12-alpine >/dev/null || { echo "Imagem ausente. Execute: sudo docker pull python:3.12-alpine"; exit 2; }
TMP="$(sudo -u labweb mktemp -d /var/lib/labgateway/uploads/smoke-XXXXXXXX)" || exit 2
cleanup(){ rm -rf -- "$TMP"; }
trap cleanup EXIT
printf 'print("LABGATEWAY_SMOKE_OK")\n' > "$TMP/main.py"
chmod 755 "$TMP"
chmod 644 "$TMP/main.py"
echo "Teste 1: executar main.py de exemplo em Docker isolado"
sudo -u labrunner env LAB_UPLOADS=/var/lib/labgateway/uploads LAB_DB=/var/lib/labgateway/labgateway.sqlite3 /opt/labgateway/.venv/bin/python - "$TMP" <<'PY'
import sys
from worker import run_container
status, output = run_container(sys.argv[1])
assert status == 'passed' and 'LABGATEWAY_SMOKE_OK' in output, (status, output)
print('OK: execucao controlada e log recebido')
PY
printf 'import time\ntime.sleep(60)\n' > "$TMP/main.py"
chmod 644 "$TMP/main.py"
echo "Teste 2: timeout e remocao do container (pode levar 15 segundos)"
sudo -u labrunner env LAB_UPLOADS=/var/lib/labgateway/uploads LAB_DB=/var/lib/labgateway/labgateway.sqlite3 /opt/labgateway/.venv/bin/python - "$TMP" <<'PY'
import sys
from worker import run_container
status, output = run_container(sys.argv[1])
assert status == 'timeout', (status, output)
print('OK: timeout e limpeza confirmada')
PY
COUNT="$(docker ps -aq --filter 'name=labgateway-' | wc -l)"
[ "$COUNT" -eq 0 ] || { echo "FALHA: contêiner residual. Verifique docker ps -a"; exit 1; }
echo "Smoke test concluido. Nenhum servico de producao foi iniciado."
