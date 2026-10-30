#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${SUDO_USER:-${USER:-philip}}"

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -- "${BASH_SOURCE[0]}" "$@"
fi

echo "Installing Homy Nginx site from ${APP_DIR}"
install -o root -g root -m 0644 "${SCRIPT_DIR}/homy.nginx.conf" /etc/nginx/sites-available/homy
ln -sfn /etc/nginx/sites-available/homy /etc/nginx/sites-enabled/homy

# Remove Basic Auth if a previous setup attempt installed it.
rm -f /etc/nginx/.htpasswd-homy

echo "Enabling the Homy user service at boot for ${TARGET_USER}"
loginctl enable-linger "${TARGET_USER}"

if ! command -v bluetoothctl >/dev/null 2>&1; then
    apt-get update
    apt-get install -y bluez
fi
systemctl enable --now bluetooth

nginx -t
systemctl reload nginx

echo "Homy Nginx site installed without Basic Auth."
echo "The app should be available at https://homy.pwrarr.com after DNS and router forwarding reach this server."
