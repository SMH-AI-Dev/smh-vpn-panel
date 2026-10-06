#!/usr/bin/env bash
# ============================================================================
#  SMH Panel - one-command installer for Ubuntu 22.04/24.04 and Debian 12
#
#  Usage (from the internet, after pushing the repo to GitHub):
#    bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh)
#
#  Or locally from the repo:   sudo bash install.sh
#
#  What it does:
#    - installs Python/Xray/WireGuard and all dependencies
#    - deploys SMH Panel as a hardened systemd service
#    - applies security & performance settings: ufw firewall, fail2ban,
#      BBR congestion control, ip_forward for WireGuard, auto security updates
#    - generates a random admin password (or uses --admin-pass) and prints it
# ============================================================================
set -Eeuo pipefail

REPO_OWNER="${SMHPANEL_REPO_OWNER:-SMH-AI-Dev}"
REPO_NAME="${SMHPANEL_REPO_NAME:-smh-vpn-panel}"
BRANCH="${SMHPANEL_BRANCH:-main}"
GH_PROXY="${SMHPANEL_GH_PROXY:-}"

DOMAIN=""
EMAIL=""
ADMIN_USER="admin"
ADMIN_PASS=""
PUBLIC_HOST=""
PANEL_PORT="2053"
WITH_TLS=1
WITH_WG=1
WG_PORT="51820"
WG_SUBNET="10.66.66.0/24"
WITH_UFW=1
WITH_FAIL2BAN=1
WITH_AUTO_UPDATES=1
SOURCE_URL="${SMHPANEL_SOURCE_URL:-}"
XRAY_VERSION="${SMHPANEL_XRAY_VERSION:-}"
CHECK_ONLY=0

APP_DIR="/opt/smhpanel"
CONF_DIR="/etc/smhpanel"
DATA_DIR="/var/lib/smhpanel"
VENV="${APP_DIR}/venv"
VENV_PY="${VENV}/bin/python"
LOG_FILE="/var/log/smhpanel-install.log"

if [[ -t 1 ]]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""; C_OFF=""
fi

say()  { printf '%s\n' "${C_BLUE}==>${C_OFF} ${C_BOLD}$*${C_OFF}"; }
ok()   { printf '%s\n' "${C_GREEN}  ✓${C_OFF} $*"; }
warn() { printf '%s\n' "${C_YELLOW}  !${C_OFF} $*" >&2; }
die()  { printf '%s\n' "${C_RED}  ✗ $*${C_OFF}" >&2; exit 1; }

usage() {
  cat <<'EOF'
SMH Panel installer

Usage: bash install.sh [options]

Options:
  --domain <domain>      Use a domain for the panel (enables Let's Encrypt via acme.sh)
  --email <email>        E-mail for Let's Encrypt registration (default: admin@<domain>)
  --public-host <host>   Public IP or domain used inside client links (auto-detected)
  --panel-port <port>    Panel port (default: 2053)
  --admin-user <name>    Admin username (default: admin)
  --admin-pass <pass>    Admin password (default: randomly generated)
  --no-tls               Serve the panel over plain HTTP (not recommended)
  --no-wireguard         Do not set up WireGuard
  --wg-port <port>       WireGuard port (default: 51820)
  --wg-subnet <cidr>     WireGuard subnet (default: 10.66.66.0/24)
  --no-ufw               Skip ufw firewall setup (not recommended)
  --no-fail2ban          Skip fail2ban setup
  --no-auto-updates      Skip unattended security updates
  --gh-proxy <prefix>    Prefix for GitHub URLs (e.g. https://ghproxy.net/)
  --source-url <url>     Override source tarball URL
  --xray-version <ver>   Install a specific Xray version (e.g. v25.6.8)
  --check                Run preflight checks only, then exit
  -h, --help             Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --email) EMAIL="${2:-}"; shift 2 ;;
    --public-host) PUBLIC_HOST="${2:-}"; shift 2 ;;
    --panel-port) PANEL_PORT="${2:-}"; shift 2 ;;
    --admin-user) ADMIN_USER="${2:-}"; shift 2 ;;
    --admin-pass) ADMIN_PASS="${2:-}"; shift 2 ;;
    --no-tls) WITH_TLS=0; shift ;;
    --no-wireguard) WITH_WG=0; shift ;;
    --wg-port) WG_PORT="${2:-}"; shift 2 ;;
    --wg-subnet) WG_SUBNET="${2:-}"; shift 2 ;;
    --no-ufw) WITH_UFW=0; shift ;;
    --no-fail2ban) WITH_FAIL2BAN=0; shift ;;
    --no-auto-updates) WITH_AUTO_UPDATES=0; shift ;;
    --gh-proxy) GH_PROXY="${2:-}"; shift 2 ;;
    --source-url) SOURCE_URL="${2:-}"; shift 2 ;;
    --xray-version) XRAY_VERSION="${2:-}"; shift 2 ;;
    --check) CHECK_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

# ------------------------------- preflight ---------------------------------
[[ $EUID -eq 0 ]] || die "please run as root (e.g. sudo bash install.sh)"

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VER="${VERSION_ID:-0}"
else
  die "cannot detect OS (/etc/os-release missing)"
fi

case "$OS_ID" in
  ubuntu)
    if [[ "${OS_VER%%.*}" -lt 22 ]]; then
      die "Ubuntu ${OS_VER} is not supported - need 22.04 or newer"
    fi
    ;;
  debian)
    if [[ "${OS_VER%%.*}" -lt 12 ]]; then
      die "Debian ${OS_VER} is not supported - need 12 or newer"
    fi
    ;;
  *)
    warn "untested OS: ${OS_ID} ${OS_VER} (continuing anyway)"
    ;;
esac

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|aarch64|arm64) : ;;
  *) die "unsupported CPU architecture: $ARCH" ;;
esac

for tool in curl tar; do
  command -v "$tool" >/dev/null 2>&1 || die "missing required tool: $tool"
done

if [[ -n "$DOMAIN" ]] && ! [[ "$DOMAIN" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ]]; then
  die "invalid domain: $DOMAIN"
fi
[[ "$PANEL_PORT" =~ ^[0-9]+$ ]] || die "invalid --panel-port"
[[ "$WG_PORT" =~ ^[0-9]+$ ]] || die "invalid --wg-port"

ok "OS: ${PRETTY_NAME:-$OS_ID $OS_VER} (${ARCH})"
ok "panel port: ${PANEL_PORT} | wireguard: $([[ $WITH_WG -eq 1 ]] && echo "on (${WG_PORT}/udp)" || echo "off")"
ok "domain: ${DOMAIN:-none (IP mode)}"

if [[ $CHECK_ONLY -eq 1 ]]; then
  say "Preflight check complete. Remove --check to install."
  exit 0
fi

mkdir -p /var/log
touch "$LOG_FILE"
chmod 600 "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1
say "Logging to ${LOG_FILE}"

export DEBIAN_FRONTEND=noninteractive

# ------------------------------ dependencies -------------------------------
say "Installing system packages…"
apt-get update -qq -y
apt-get install -y -qq --no-install-recommends \
  python3 python3-venv python3-pip sqlite3 curl unzip jq \
  ufw fail2ban socat wireguard-tools ca-certificates iproute2 iptables cron >/dev/null
ok "packages installed"

# ------------------------------- system user -------------------------------
if ! id -u smhpanel >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin smhpanel
  ok "created system user: smhpanel"
else
  ok "system user smhpanel already exists"
fi

mkdir -p "$APP_DIR" "$CONF_DIR" "$DATA_DIR" "${CONF_DIR}/certs"

# -------------------------------- source -----------------------------------
say "Fetching SMH Panel source…"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
if [[ -n "$SCRIPT_DIR" && -f "${SCRIPT_DIR}/app/requirements.txt" ]]; then
  SRC="$SCRIPT_DIR"
  ok "using local repository: $SRC"
else
  TARBALL_URL="${SOURCE_URL:-https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.tar.gz}"
  [[ -n "$GH_PROXY" ]] && TARBALL_URL="${GH_PROXY}${TARBALL_URL}"
  say "downloading ${TARBALL_URL}"
  curl -fsSL --retry 3 --connect-timeout 20 "$TARBALL_URL" -o /tmp/smhpanel-src.tar.gz \
    || die "source download failed - check network or use --gh-proxy/--source-url"
  rm -rf /tmp/smhpanel-src
  mkdir -p /tmp/smhpanel-src
  tar -xzf /tmp/smhpanel-src.tar.gz -C /tmp/smhpanel-src --strip-components=1 \
    || die "failed to extract source archive"
  SRC="/tmp/smhpanel-src"
  ok "source downloaded"
fi

rm -rf "${APP_DIR}/app"
cp -r "${SRC}/app" "${APP_DIR}/app"
ok "application deployed to ${APP_DIR}/app"

say "Creating Python virtualenv…"
python3 -m venv "$VENV"
"${VENV}/bin/pip" install --quiet --upgrade pip
PIP_INDEX_ARGS=()
if [[ -n "${SMHPANEL_PIP_INDEX:-}" ]]; then
  PIP_INDEX_ARGS=(-i "$SMHPANEL_PIP_INDEX")
fi
"${VENV}/bin/pip" install --quiet "${PIP_INDEX_ARGS[@]}" -r "${APP_DIR}/app/requirements.txt"
ok "Python dependencies installed"

# -------------------------------- helpers ----------------------------------
say "Installing privileged helpers…"
for helper in "${SRC}/deploy/helpers/"*; do
  name="$(basename "$helper")"
  install -o root -g root -m 755 "$helper" "/usr/local/sbin/${name}"
done
install -o root -g root -m 440 "${SRC}/deploy/sudoers/smhpanel.sudoers" /etc/sudoers.d/smhpanel
visudo -cf /etc/sudoers.d/smhpanel >/dev/null || die "sudoers file validation failed"
ok "helpers + sudoers installed"

# --------------------------------- xray ------------------------------------
say "Installing Xray-core…"
install_xray_manual() {
  local arch="64"
  [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]] && arch="arm64-v8a"
  local url="https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-${arch}.zip"
  [[ -n "$XRAY_VERSION" ]] && url="https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-${arch}.zip"
  say "manual Xray download: ${url}"
  curl -fsSL --retry 3 "${GH_PROXY}${url}" -o /tmp/xray.zip || return 1
  rm -rf /tmp/xray-bin && mkdir -p /tmp/xray-bin
  unzip -o -q /tmp/xray.zip -d /tmp/xray-bin || return 1
  install -m 755 /tmp/xray-bin/xray /usr/local/bin/xray || return 1
  getent passwd xray >/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin xray
  install -d -m 755 /usr/local/etc/xray
  cat > /etc/systemd/system/xray.service <<'XRAY_UNIT'
[Unit]
Description=Xray Service
After=network.target nss-lookup.target

[Service]
User=xray
Group=xray
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
XRAY_UNIT
  systemctl daemon-reload
  systemctl enable xray >/dev/null 2>&1 || true
  return 0
}

XRAY_OK=0
if [[ -x /usr/local/bin/xray ]]; then
  ok "Xray already installed (updating…)"
fi
if curl -fsSL --retry 2 --connect-timeout 20 "${GH_PROXY}https://github.com/XTLS/Xray-install/raw/main/install-release.sh" \
     -o /tmp/xray-install.sh 2>/dev/null; then
  if [[ -n "$XRAY_VERSION" ]]; then
    bash /tmp/xray-install.sh install --version "$XRAY_VERSION" >/dev/null 2>&1 \
      || bash /tmp/xray-install.sh install >/dev/null 2>&1 || true
  else
    bash /tmp/xray-install.sh install >/dev/null 2>&1 || true
  fi
  [[ -x /usr/local/bin/xray ]] && XRAY_OK=1
fi
if [[ $XRAY_OK -ne 1 ]]; then
  warn "official Xray installer failed; trying manual download"
  if install_xray_manual; then
    XRAY_OK=1
  fi
fi
if [[ $XRAY_OK -eq 1 ]]; then
  ok "Xray installed: $(/usr/local/bin/xray version 2>/dev/null | head -n1 || echo unknown)"
else
  warn "Xray could not be installed automatically — install it later and run: smhpanel-xray-apply"
fi

# The modern official installer runs Xray as user "nobody"; adapt it to a
# dedicated xray user so the panel can keep the config at 0640 root:xray.
if [[ -f /etc/systemd/system/xray.service ]] && grep -q "^User=nobody" /etc/systemd/system/xray.service; then
  getent group xray >/dev/null 2>&1 || groupadd --system xray
  getent passwd xray >/dev/null 2>&1 || useradd --system --gid xray --no-create-home --shell /usr/sbin/nologin xray
  sed -i "s/^User=nobody$/User=xray/" /etc/systemd/system/xray.service
  grep -q "^Group=" /etc/systemd/system/xray.service || sed -i "/^User=xray$/a Group=xray" /etc/systemd/system/xray.service
  systemctl daemon-reload
fi

# ------------------------------ memory tuning ------------------------------
say "Applying kernel/network tuning (BBR, forwarding)…"
install -m 644 "${SRC}/deploy/sysctl/99-smhpanel.conf" /etc/sysctl.d/99-smhpanel.conf
sysctl --system >/dev/null 2>&1 || true
ok "sysctl applied"

if [[ $WITH_WG -eq 1 ]]; then
  echo "wireguard" > /etc/modules-load.d/wireguard.conf
  modprobe wireguard 2>/dev/null || warn "wireguard module load failed (kernel may need reboot)"
fi

# ------------------------------ public host --------------------------------
if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$(curl -fsS4 --max-time 8 https://api.ipify.org 2>/dev/null || true)"
fi
if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$(curl -fsS4 --max-time 8 https://ifconfig.me 2>/dev/null || true)"
fi
if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
[[ -n "$DOMAIN" ]] && PUBLIC_HOST="$DOMAIN"
[[ -n "$PUBLIC_HOST" ]] || die "could not detect public host - pass --public-host"
ok "public host: ${PUBLIC_HOST}"

# ----------------------------- panel init ----------------------------------
say "Initializing SMH Panel (database, admin, keys, configs)…"
chown -R smhpanel:smhpanel "$APP_DIR" "$CONF_DIR" "$DATA_DIR"

INIT_ARGS=(
  --config "${CONF_DIR}/config.json"
  --admin-user "$ADMIN_USER"
  --panel-port "$PANEL_PORT"
  --public-host "$PUBLIC_HOST"
  --non-interactive
)
[[ -n "$ADMIN_PASS" ]] && INIT_ARGS+=(--admin-pass "$ADMIN_PASS")
[[ $WITH_TLS -eq 0 ]] && INIT_ARGS+=(--no-tls)
if [[ $WITH_WG -eq 1 ]]; then
  INIT_ARGS+=(--wg-port "$WG_PORT" --wg-subnet "$WG_SUBNET")
else
  INIT_ARGS+=(--no-wireguard)
fi

set +e
INIT_OUT="$(cd "${APP_DIR}/app" && sudo -u smhpanel -H "$VENV_PY" -m smhpanel.cli init "${INIT_ARGS[@]}" 2>&1)"
INIT_RC=$?
set -e
echo "$INIT_OUT"
[[ $INIT_RC -eq 0 ]] || die "panel initialization failed (see log)"
ok "panel initialized"

# Let the Xray service user read TLS materials; keep private keys strict (0640).
# The panel user is added to the xray group so both uvicorn (TLS listener) and
# Xray (TLS inbounds) can read the same certificates.
if [[ -d "${CONF_DIR}/certs" ]]; then
  if getent group xray >/dev/null 2>&1; then
    chown -R root:xray "${CONF_DIR}/certs" 2>/dev/null || true
    getent passwd smhpanel >/dev/null 2>&1 && usermod -aG xray smhpanel 2>/dev/null || true
  fi
  chmod 755 "${CONF_DIR}/certs" 2>/dev/null || true
  find "${CONF_DIR}/certs" -name "*.crt" -exec chmod 644 {} + 2>/dev/null || true
  find "${CONF_DIR}/certs" -name "*.key" -exec chmod 640 {} + 2>/dev/null || true
fi

GENERATED_PASS="$(printf '%s\n' "$INIT_OUT" | grep -m1 '^SMHPANEL_ADMIN_PASSWORD=' | cut -d= -f2- || true)"

# ------------------------------ certificate --------------------------------
if [[ -n "$DOMAIN" && $WITH_TLS -eq 1 ]]; then
  say "Obtaining Let's Encrypt certificate for ${DOMAIN}…"
  if [[ ! -x /root/.acme.sh/acme.sh ]]; then
    curl -fsSL --retry 2 "${GH_PROXY}https://get.acme.sh" | sh -s "email=${EMAIL:-admin@${DOMAIN}}" >/dev/null 2>&1 \
      || warn "acme.sh installation failed"
  fi
  if [[ -x /root/.acme.sh/acme.sh ]]; then
    /usr/local/sbin/smhpanel-cert-issue "$DOMAIN" || warn "certificate issuance failed - check DNS and port 80"
  fi
fi

# ------------------------------- services ----------------------------------
say "Installing systemd service…"
install -m 644 "${SRC}/deploy/systemd/smhpanel.service" /etc/systemd/system/smhpanel.service
systemctl daemon-reload
systemctl enable smhpanel >/dev/null 2>&1 || true
systemctl restart smhpanel
sleep 3
if systemctl is-active --quiet smhpanel; then
  ok "SMH Panel service is running"
else
  warn "SMH Panel service did not start cleanly - inspect: journalctl -u smhpanel -n 50"
fi

# --------------------------------- ufw -------------------------------------
if [[ $WITH_UFW -eq 1 ]]; then
  say "Configuring firewall (ufw)…"
  SSH_PORT="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}' || true)"
  SSH_PORT="${SSH_PORT:-22}"
  ufw default deny incoming >/dev/null
  ufw default allow outgoing >/dev/null
  ufw allow "${SSH_PORT}/tcp" >/dev/null
  ufw allow "${PANEL_PORT}/tcp" >/dev/null
  ufw allow 80/tcp >/dev/null
  if [[ $WITH_WG -eq 1 ]]; then
    ufw allow "${WG_PORT}/udp" >/dev/null
  fi
  ufw --force enable >/dev/null
  ok "ufw enabled (ssh:${SSH_PORT}, panel:${PANEL_PORT}, 80/tcp$([[ $WITH_WG -eq 1 ]] && echo ", wg:${WG_PORT}/udp"))"
else
  warn "ufw setup skipped"
fi

# ------------------------------- fail2ban ----------------------------------
if [[ $WITH_FAIL2BAN -eq 1 ]]; then
  say "Configuring fail2ban…"
  install -d -m 755 /etc/fail2ban/jail.d
  install -m 644 "${SRC}/deploy/fail2ban/jail.local" /etc/fail2ban/jail.d/smhpanel.local
  systemctl enable fail2ban >/dev/null 2>&1 || true
  systemctl restart fail2ban || warn "fail2ban restart failed"
  ok "fail2ban active (sshd jail: 5 retries -> 1h ban)"
fi

# --------------------------- auto security updates --------------------------
if [[ $WITH_AUTO_UPDATES -eq 1 ]]; then
  say "Enabling unattended security updates…"
  apt-get install -y -qq unattended-upgrades >/dev/null 2>&1 || true
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
  systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true
  ok "auto security updates enabled (no automatic reboots)"
fi

# ------------------------------ credentials --------------------------------
CRED_FILE="/root/smhpanel-credentials.txt"
SCHEME="https"
[[ $WITH_TLS -eq 0 ]] && SCHEME="http"
{
  echo "SMH Panel credentials"
  echo "====================="
  echo "URL:      ${SCHEME}://${PUBLIC_HOST}:${PANEL_PORT}"
  echo "User:     ${ADMIN_USER}"
  if [[ -z "$GENERATED_PASS" || "$GENERATED_PASS" == "***" ]]; then
    echo "Password: (unchanged from previous install)"
  else
    echo "Password: ${GENERATED_PASS}"
  fi
  echo ""
  echo "Database: ${DATA_DIR}/smhpanel.db"
  echo "Change the password from the panel: Settings -> Change password"
} > "$CRED_FILE"
chmod 600 "$CRED_FILE"

# -------------------------------- summary ----------------------------------
echo
echo "${C_GREEN}${C_BOLD}==================================================================${C_OFF}"
echo "${C_GREEN}${C_BOLD}  ✅ SMH Panel installed successfully${C_OFF}"
echo "${C_GREEN}${C_BOLD}==================================================================${C_OFF}"
echo "  Panel URL      : ${C_BOLD}${SCHEME}://${PUBLIC_HOST}:${PANEL_PORT}${C_OFF}"
echo "  Admin user     : ${ADMIN_USER}"
if [[ -z "$GENERATED_PASS" || "$GENERATED_PASS" == "***" ]]; then
  echo "  Admin password : (unchanged - see ${CRED_FILE})"
else
  echo "  Admin password : ${C_BOLD}${GENERATED_PASS}${C_OFF}"
fi
echo "  Credentials    : ${CRED_FILE}"
echo
echo "  Services       : smhpanel | xray | wg-quick@wg0 | fail2ban | ufw"
echo "  Logs           : journalctl -u smhpanel -f   /   journalctl -u xray -f"
echo "  CLI            : smhpanel status | smhpanel backup --out /root/backup.tar.gz"
echo
echo "  Next steps:"
echo "   1) open the panel URL and log in"
echo "   2) create a VLESS + Reality inbound (recommended, port 443)"
echo "   3) add clients and import the links/QR into your VPN app"
echo
if [[ $WITH_TLS -eq 1 && -z "$DOMAIN" ]]; then
  echo "  ${C_YELLOW}Note:${C_OFF} no domain was provided, so the panel uses a self-signed"
  echo "  certificate. For clean HTTPS (and easier subscription downloads),"
  echo "  point a domain at this server and re-run the installer with --domain."
  echo
fi
echo "  Docs: README.md and docs/ in the repository."
echo "${C_GREEN}${C_BOLD}==================================================================${C_OFF}"
