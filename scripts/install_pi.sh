#!/usr/bin/env bash
# LabGateway Pi3 installer. Requires explicit --install and never changes forno.service.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---check}"
die(){ printf 'ERRO: %s\n' "$*" >&2; exit 1; }
[ "$MODE" = "--check" ] || [ "$MODE" = "--install" ] || die "Uso: bash scripts/install_pi.sh --check | --install"
echo "LabGateway: verificacao do equipamento"
ARCH="$(uname -m)"
echo "Arquitetura: $ARCH"
case "$ARCH" in aarch64|armv7l) ;; *) die "Arquitetura nao homologada: $ARCH";; esac
command -v python3 >/dev/null || die "Python 3 ausente."
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python >= 3.10 requerido"' || die "Python antigo. Nao atualize o sistema do forno sem backup."
command -v docker >/dev/null || die "Docker nao instalado. Avalie compatibilidade do sistema antes de instalar."
if ! docker info >/dev/null 2>&1; then
  if [ "$MODE" = "--install" ]; then
    die "Docker daemon nao funcional. Verifique manualmente."
  fi
  echo "AVISO: usuario sem acesso ao daemon Docker, ou daemon parado. Validar com sudo antes da instalacao."
fi
[ -f "$ROOT/app.py" ] || die "Execute de dentro do repositorio LabGateway."
echo "Arquitetura e Python: OK; Docker encontrado (acesso ao daemon deve ser confirmado)"
if [ "$MODE" = "--install" ]; then
  docker image inspect python:3.12-alpine >/dev/null 2>&1 || die "Falta a imagem Python. Antes da instalacao execute: sudo docker pull python:3.12-alpine"
  echo "Confirmando limite real de 128 MiB no Docker..."
  LIMIT="$(docker run --rm --network none --memory 128m --memory-swap 128m python:3.12-alpine cat /sys/fs/cgroup/memory.max 2>/dev/null)" || die "Docker falhou no teste de cgroup."
  [ "$LIMIT" = "134217728" ] || die "Limite Docker nao aplicado (obtido: $LIMIT). Instalacao bloqueada."
  echo "Limite real de memoria: OK"
fi
echo "Servicos antigos:"
for SERVICE in forno.service ngrok.service; do echo "$SERVICE: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"; done
if [ "$MODE" = "--check" ]; then
  echo "Verificacao concluida. Nada foi instalado nem modificado."
  exit 0
fi
[ "$(id -u)" -eq 0 ] || die "Use sudo somente com --install."
command -v useradd >/dev/null || die "useradd ausente"
[ ! -e /opt/labgateway ] || die "/opt/labgateway ja existe. Instalacao interrompida para nao sobrescrever."
[ ! -e /etc/labgateway ] || die "/etc/labgateway ja existe. Instalacao interrompida para nao sobrescrever."
[ ! -e /var/lib/labgateway ] || die "/var/lib/labgateway ja existe. Instalacao interrompida para nao sobrescrever."
for svc in labgateway-web.service labgateway-worker.service; do
  [ ! -e "/etc/systemd/system/$svc" ] || die "Servico existente: $svc. Nao sobrescrevendo."
done
getent group labdata >/dev/null || groupadd --system labdata
id -u labweb >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin --gid labdata labweb
id -u labrunner >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin --gid labdata labrunner
getent group docker >/dev/null || die "Grupo docker inexistente."
getent group labdata >/dev/null || die "Grupo labdata ausente."
usermod -a -G docker labrunner
mkdir -p /opt/labgateway /etc/labgateway /var/lib/labgateway/uploads
cp -a "$ROOT/." /opt/labgateway/
chown -R root:root /opt/labgateway
chmod -R go-w /opt/labgateway
chmod 755 /opt/labgateway
chown -R labweb:labdata /var/lib/labgateway
chmod 2770 /var/lib/labgateway /var/lib/labgateway/uploads
umask 027
python3 -m venv /opt/labgateway/.venv || die "python3-venv requerido. Servicos ainda nao foram iniciados."
/opt/labgateway/.venv/bin/python -m pip install -r /opt/labgateway/requirements.txt
SECRET="$(/opt/labgateway/.venv/bin/python -c 'import secrets;print(secrets.token_hex(32))')"
cat > /etc/labgateway/web.env <<EOF
LAB_SECRET_KEY=$SECRET
LAB_DB=/var/lib/labgateway/labgateway.sqlite3
LAB_UPLOADS=/var/lib/labgateway/uploads
LAB_SECURE_COOKIE=0
EOF
chmod 600 /etc/labgateway/web.env
chown root:root /etc/labgateway/web.env
install -m 644 /opt/labgateway/deploy/labgateway-web.service /etc/systemd/system/
install -m 644 /opt/labgateway/deploy/labgateway-worker.service /etc/systemd/system/
systemctl daemon-reload
echo "Arquivos instalados. Servicos NAO foram iniciados."
echo "Crie o professor via scripts/create_pi_user.sh, execute os testes e valide o firewall antes de iniciar os servicos."
