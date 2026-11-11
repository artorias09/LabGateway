#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="/opt/labgateway"
DATA="/var/lib/labgateway"
ENVFILE="/etc/labgateway/web.env"
STAMP="$(date +%Y%m%d-%H%M%S)"

die(){ printf 'ERRO: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Execute com sudo."
[ -f "$ROOT/app.py" ] || die "Execute o script a partir do repositorio atualizado."
[ -d "$TARGET" ] || die "LabGateway instalado não encontrado em $TARGET."
[ -f "$DATA/labgateway.sqlite3" ] || die "Banco atual não encontrado."
[ -f "$ENVFILE" ] || die "Arquivo de ambiente não encontrado."

echo "Backup do banco..."
cp -a "$DATA/labgateway.sqlite3" "$DATA/labgateway.sqlite3.bak-$STAMP"

echo "Preparando armazenamento de dados experimentais..."
mkdir -p "$DATA/datasets"
chown labweb:labdata "$DATA/datasets"
chmod 2770 "$DATA/datasets"

if ! grep -q '^LAB_DATASETS=' "$ENVFILE"; then
  printf '\nLAB_DATASETS=/var/lib/labgateway/datasets\n' >> "$ENVFILE"
fi

echo "Parando somente os serviços do LabGateway..."
systemctl stop labgateway-worker.service labgateway-web.service

echo "Atualizando aplicação..."
for item in app.py admin.py core.py datasets.py store.py worker.py requirements.txt templates static docker scripts deploy docs README.md; do
  if [ -e "$ROOT/$item" ]; then
    rm -rf "$TARGET/$item"
    cp -a "$ROOT/$item" "$TARGET/$item"
  fi
done
chown -R root:root "$TARGET"
chmod -R go-w "$TARGET"
chmod 755 "$TARGET"

"$TARGET/.venv/bin/python" -m pip install -r "$TARGET/requirements.txt"

echo "Inicializando esquema do banco..."
set -a
. "$ENVFILE"
set +a
sudo -u labweb env   LAB_DB="$LAB_DB"   LAB_UPLOADS="$LAB_UPLOADS"   LAB_DATASETS="$LAB_DATASETS"   "$TARGET/.venv/bin/python" -c 'import store; store.init()'

echo "Iniciando LabGateway..."
systemctl start labgateway-web.service labgateway-worker.service
systemctl is-active --quiet labgateway-web.service || die "labgateway-web não iniciou."
systemctl is-active --quiet labgateway-worker.service || die "labgateway-worker não iniciou."

echo "Atualização concluída."
echo "Backup: $DATA/labgateway.sqlite3.bak-$STAMP"
echo "forno.service não foi alterado."
