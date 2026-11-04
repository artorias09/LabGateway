#!/usr/bin/env bash
# Somente leitura. Nao altera rede, forno, ngrok ou arquivos.
set -u
echo "=== LABGATEWAY PREFLIGHT (SOMENTE LEITURA) ==="
echo "[host]"; hostname; uname -m; uname -r
echo "[OS]"; if [ -r /etc/os-release ]; then grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release; fi
echo "[memoria]"; free -h
echo "[disco]"; df -h /
echo "[rede]"; hostname -I 2>/dev/null || true
if command -v nmcli >/dev/null 2>&1; then nmcli -t -f NAME,TYPE,DEVICE connection show --active || true; fi
echo "[pacotes]"; for cmd in python3 git docker ngrok; do
  if command -v "$cmd" >/dev/null 2>&1; then command -v "$cmd"; else echo "$cmd: AUSENTE"; fi
done
echo "[python]"; python3 --version 2>&1 || true
echo "[docker]"; if command -v docker >/dev/null 2>&1; then docker --version; docker info --format '{{.Architecture}} {{.CgroupDriver}}' 2>&1 || true; fi
echo "[servicos]"; for svc in forno.service flask-app.service ngrok.service notify-link.service url-watcher.service docker.service ssh.service; do
  echo "$svc: $(systemctl is-active "$svc" 2>/dev/null || true)"
done
echo "[portas HTTP 5000/5001]"; if command -v ss >/dev/null 2>&1; then ss -ltn '( sport = :5000 or sport = :5001 )' 2>/dev/null || true; fi
echo "=== FIM. NENHUMA CONFIGURACAO FOI ALTERADA ==="
