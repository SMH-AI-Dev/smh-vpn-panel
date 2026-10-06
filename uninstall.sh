#!/usr/bin/env bash
# SMH Panel uninstaller. Use --purge to also delete data and the service user.
set -Eeuo pipefail

PURGE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge) PURGE=1; shift ;;
    -h|--help)
      cat <<'EOF'
SMH Panel uninstaller

Usage: bash uninstall.sh [--purge]

  (default)  stop and remove the panel service and helper scripts, keep data
  --purge    also remove /opt/smhpanel, /etc/smhpanel, /var/lib/smhpanel,
             the wireguard config and the smhpanel system user
EOF
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "please run as root" >&2
  exit 1
fi

echo "==> stopping and disabling services"
systemctl disable --now smhpanel >/dev/null 2>&1 || true
rm -f /etc/systemd/system/smhpanel.service
systemctl daemon-reload >/dev/null 2>&1 || true

echo "==> removing helper scripts and sudoers entry"
rm -f /usr/local/sbin/smhpanel-firewall-open \
      /usr/local/sbin/smhpanel-firewall-close \
      /usr/local/sbin/smhpanel-firewall-status \
      /usr/local/sbin/smhpanel-xray-apply \
      /usr/local/sbin/smhpanel-wg-apply \
      /usr/local/sbin/smhpanel-wg-show \
      /usr/local/sbin/smhpanel-service \
      /usr/local/sbin/smhpanel-cert-issue \
      /usr/local/sbin/smhpanel-cert-renew
rm -f /etc/sudoers.d/smhpanel

if [[ $PURGE -eq 1 ]]; then
  echo "==> purging panel data"
  systemctl disable --now "wg-quick@wg0" >/dev/null 2>&1 || true
  rm -rf /opt/smhpanel /etc/smhpanel /var/lib/smhpanel /etc/wireguard/wg0.conf
  userdel smhpanel >/dev/null 2>&1 || true
  echo "Purged. Xray, ufw rules, fail2ban and its jails were left untouched."
else
  echo "Panel removed. Data kept at /etc/smhpanel and /var/lib/smhpanel."
  echo "Run with --purge to delete data as well."
fi
