#!/usr/bin/env bash
set -Eeuo pipefail
[ "$#" -eq 2 ] || { echo "Uso: sudo bash scripts/create_pi_user.sh professor teacher"; exit 2; }
case "$2" in teacher|student) ;; *) echo "Papel invalido"; exit 2;; esac
[ "$(id -u)" -eq 0 ] || { echo "Execute com sudo"; exit 2; }
[ -d /opt/labgateway/.venv ] || { echo "LabGateway nao instalado"; exit 2; }
cd /opt/labgateway
sudo -u labweb env LAB_DB=/var/lib/labgateway/labgateway.sqlite3 LAB_UPLOADS=/var/lib/labgateway/uploads /opt/labgateway/.venv/bin/python admin.py create-user "$1" "$2"
