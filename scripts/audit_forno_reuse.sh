#!/usr/bin/env bash
# Auditoria somente leitura. Nao extrai certificados, senhas ou tokens.
set -u
printf '%s\n' '=== INFRAESTRUTURA EXISTENTE: FORNO -> LABGATEWAY ==='
echo '[sistema]'; uname -m; python3 --version 2>&1 || true
if test -r /etc/os-release; then grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release; fi
echo '[recursos]'; free -h; df -h /
echo '[interfaces ativas, sem credenciais]'
ip -br link 2>/dev/null || true
echo '[rota padrao: so identificacao de interface]'
ip -o route show default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev") print "interface de saida:",$(i+1)}' | sort -u
echo '[servicos existentes]'
for svc in forno.service flask-app.service ngrok.service notify-link.service url-watcher.service docker.service ssh.service; do
  load="$(systemctl show -p LoadState --value "$svc" 2>/dev/null || true)"
  active="$(systemctl is-active "$svc" 2>/dev/null || true)"
  if [ "$load" != "not-found" ]; then echo "$svc: $load / $active"; fi
done
echo '[porta 5000, 5001, 4040: sem endereco remoto]'
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | awk 'NR==1 || $4 ~ /:(5000|5001|4040)$/ {print}'
fi
echo '[resposta local HTTP]'
if command -v curl >/dev/null 2>&1; then
  for port in 5000 5001; do
    code="$(curl --max-time 3 --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$port/" || true)"
    echo "localhost:$port HTTP ${code:-indisponivel}"
  done
fi
echo '[ngrok: binario e API local, sem imprimir enderecos e tokens]'
if command -v ngrok >/dev/null 2>&1; then ngrok version 2>&1 || true; else echo 'ngrok nao encontrado no PATH'; fi
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import json, urllib.request
try:
    req=urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
    with urllib.request.urlopen(req,timeout=2) as r:
        obj=json.load(r)
    print("API ngrok ativa; tuneis:",len(obj.get("tunnels",[])))
except Exception:
    print("API ngrok indisponivel na porta 4040; isso nao prova que o tunnel esta parado")
PY
fi
echo '[instalacoes locais, so existencia]'
for path in /home/kelvin/Downloads/forno /home/kelvin/forno /opt/labgateway /var/lib/labgateway; do
  if [ -e "$path" ]; then echo "existe: $path"; fi
done
echo '=== FIM. NADA FOI ALTERADO. NAO ENVIE ARQUIVOS DE CERTIFICADOS/TOKENS. ==='
