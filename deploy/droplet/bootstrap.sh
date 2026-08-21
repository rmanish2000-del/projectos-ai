#!/usr/bin/env bash
# Idempotent bootstrap: bare Ubuntu 24.04 -> ProjectOS fleet node.
# Safe to run twice. Requires founder-placed secret files; never creates secret values.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

PROJECTOS_USER=projectos
REPO_URL="git@github.com:rmanish2000-del/projectos-ai.git"
OPT_ROOT=/opt/projectos
REPO_DIR="${OPT_ROOT}/projectos-ai"
VENV_DIR="${OPT_ROOT}/venv"
STATE_DIR=/var/lib/projectos
SECRETS_DIR=/etc/projectos/secrets
DEPLOY_KEY="${SECRETS_DIR}/github-deploy-key"
GDRIVE_SA="${SECRETS_DIR}/gdrive-sa.json"
INBOX_KEY="${SECRETS_DIR}/k1"
CODEX_ENV="${SECRETS_DIR}/codex.env"
RCLONE_CONFIG=/etc/projectos/rclone.conf
REPORTS_DIR=/mnt/gdrive/AGENT-REPORTS
INBOX_DIR=/home/projectos/gdrive-inbox
UNIT_SRC="${REPO_DIR}/deploy/droplet/systemd"

require_file() {
  if [[ ! -s "$1" ]]; then
    echo "Required file missing or empty: $1" >&2
    exit 2
  fi
}

require_file "${DEPLOY_KEY}"
require_file "${GDRIVE_SA}"
require_file "${INBOX_KEY}"
require_file "${CODEX_ENV}"
if ! grep -qE '^[[:space:]]*(export[[:space:]]+)?CODEX_API_KEY=' "${CODEX_ENV}"; then
  echo "${CODEX_ENV} must define CODEX_API_KEY" >&2
  exit 2
fi

echo "==> system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git curl ca-certificates python3 python3-pip python3-venv \
  fail2ban unattended-upgrades ufw rclone fuse3

echo "==> unattended upgrades"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> fail2ban"
systemctl enable --now fail2ban

echo "==> sshd: disable password auth (idempotent)"
SSHD=/etc/ssh/sshd_config
if grep -qE '^PasswordAuthentication' "${SSHD}"; then
  sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD}"
else
  echo 'PasswordAuthentication no' >> "${SSHD}"
fi
if grep -qE '^KbdInteractiveAuthentication' "${SSHD}"; then
  sed -i 's/^KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' "${SSHD}"
else
  echo 'KbdInteractiveAuthentication no' >> "${SSHD}"
fi
if systemctl reload ssh; then
  :
else
  systemctl reload sshd
fi

echo "==> service user ${PROJECTOS_USER}"
if ! id -u "${PROJECTOS_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "${PROJECTOS_USER}"
fi

echo "==> directories"
mkdir -p "${OPT_ROOT}" "${STATE_DIR}" "${STATE_DIR}/failures" "${SECRETS_DIR}" \
  "${REPORTS_DIR}" "${INBOX_DIR}" "/home/${PROJECTOS_USER}/.projectos"
chown -R "${PROJECTOS_USER}:${PROJECTOS_USER}" "${OPT_ROOT}" "${STATE_DIR}"
chmod 700 "${SECRETS_DIR}"
chown root:root "${SECRETS_DIR}"
# projectos needs read on secrets files the founder will drop
chmod 750 "${SECRETS_DIR}"
chgrp "${PROJECTOS_USER}" "${SECRETS_DIR}"
chmod 600 "${DEPLOY_KEY}" "${GDRIVE_SA}" "${INBOX_KEY}"
chown "${PROJECTOS_USER}:${PROJECTOS_USER}" "${DEPLOY_KEY}" "${GDRIVE_SA}" "${INBOX_KEY}"
install -o "${PROJECTOS_USER}" -g "${PROJECTOS_USER}" -m 0600 \
  "${INBOX_KEY}" "/home/${PROJECTOS_USER}/.projectos/inbox.key"
chown "${PROJECTOS_USER}:${PROJECTOS_USER}" "${REPORTS_DIR}" "${INBOX_DIR}" "/home/${PROJECTOS_USER}/.projectos"

echo "==> clone / update repo"
if [[ -d "${REPO_DIR}/.git" ]]; then
  runuser -u "${PROJECTOS_USER}" -- env GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git -C "${REPO_DIR}" fetch --all --prune
  runuser -u "${PROJECTOS_USER}" -- git -C "${REPO_DIR}" checkout main
  runuser -u "${PROJECTOS_USER}" -- env GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git -C "${REPO_DIR}" pull --ff-only origin main
else
  runuser -u "${PROJECTOS_USER}" -- env GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git clone "${REPO_URL}" "${REPO_DIR}"
fi
chmod +x "${REPO_DIR}/deploy/droplet/wake-linux.sh" "${REPO_DIR}/deploy/droplet/bootstrap.sh"

echo "==> python virtual environment"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
if [[ -f "${REPO_DIR}/pyproject.toml" ]] || [[ -f "${REPO_DIR}/setup.py" ]]; then
  "${VENV_DIR}/bin/python" -m pip install -e "${REPO_DIR}"
fi
chown -R "${PROJECTOS_USER}:${PROJECTOS_USER}" "${VENV_DIR}"

echo "==> rclone service-account configuration"
install -d -o root -g "${PROJECTOS_USER}" -m 0750 /etc/projectos
cat > "${RCLONE_CONFIG}" <<EOF
[fleet]
type = drive
scope = drive
service_account_file = ${GDRIVE_SA}
shared_with_me = true
EOF
chown root:"${PROJECTOS_USER}" "${RCLONE_CONFIG}"
chmod 0640 "${RCLONE_CONFIG}"

echo "==> install systemd units"
for f in projectos-wake.service projectos-wake.timer projectos-signer.service projectos-signer.timer projectos-outreach-watch.service projectos-outreach-watch.timer projectos-reports-mount.service projectos-inbox-mount.service projectos-seat@.service projectos-seat@.timer; do
  install -m 0644 "${UNIT_SRC}/${f}" "/etc/systemd/system/${f}"
done
systemctl daemon-reload
systemctl enable --now projectos-reports-mount.service projectos-inbox-mount.service
# Timers not enabled here — founder enables after secrets are in place (see HANDOFF.md)

echo "==> resource note"
echo "Host profile: 1 vCPU / 1 GB RAM / 25 GB disk."
echo "This node is sized for wake + signer only."
echo "Dhan tape recorder: NOT installed here — footprint unmeasured; do not co-locate until measured."

echo "BOOTSTRAP OK"
echo "Next: place secrets per deploy/droplet/SECRETS.md, then enable timers per HANDOFF.md"
