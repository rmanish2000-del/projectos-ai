#!/usr/bin/env bash
# Idempotent bootstrap: bare Ubuntu 24.04 -> ProjectOS fleet node.
# Safe to run twice. Does NOT place secrets. Does NOT enable timers until founder places secrets.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

PROJECTOS_USER=projectos
REPO_URL="https://github.com/rmanish2000-del/projectos-ai.git"
OPT_ROOT=/opt/projectos
REPO_DIR="${OPT_ROOT}/projectos-ai"
STATE_DIR=/var/lib/projectos
SECRETS_DIR=/etc/projectos/secrets
UNIT_SRC="${REPO_DIR}/deploy/droplet/systemd"

echo "==> system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git curl ca-certificates python3 python3-pip python3-venv \
  fail2ban unattended-upgrades ufw

echo "==> unattended upgrades"
dpkg-reconfigure -f noninteractive unattended-upgrades || true

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
systemctl reload ssh || systemctl reload sshd || true

echo "==> service user ${PROJECTOS_USER}"
if ! id -u "${PROJECTOS_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "${PROJECTOS_USER}"
fi

echo "==> directories"
mkdir -p "${OPT_ROOT}" "${STATE_DIR}" "${STATE_DIR}/failures" "${SECRETS_DIR}"
chown -R "${PROJECTOS_USER}:${PROJECTOS_USER}" "${OPT_ROOT}" "${STATE_DIR}"
chmod 700 "${SECRETS_DIR}"
chown root:root "${SECRETS_DIR}"
# projectos needs read on secrets files the founder will drop
chmod 750 "${SECRETS_DIR}"
chgrp "${PROJECTOS_USER}" "${SECRETS_DIR}"

echo "==> clone / update repo"
if [[ -d "${REPO_DIR}/.git" ]]; then
  sudo -u "${PROJECTOS_USER}" git -C "${REPO_DIR}" fetch --all --prune
  sudo -u "${PROJECTOS_USER}" git -C "${REPO_DIR}" checkout main
  sudo -u "${PROJECTOS_USER}" git -C "${REPO_DIR}" pull --ff-only origin main || true
else
  sudo -u "${PROJECTOS_USER}" git clone "${REPO_URL}" "${REPO_DIR}"
fi
chmod +x "${REPO_DIR}/deploy/droplet/wake-linux.sh" "${REPO_DIR}/deploy/droplet/bootstrap.sh"

echo "==> python package (editable if pyproject present)"
if [[ -f "${REPO_DIR}/pyproject.toml" ]] || [[ -f "${REPO_DIR}/setup.py" ]]; then
  sudo -u "${PROJECTOS_USER}" python3 -m pip install --user -e "${REPO_DIR}" || \
    sudo -u "${PROJECTOS_USER}" python3 -m pip install --user "${REPO_DIR}" || true
fi

echo "==> install systemd units"
for f in projectos-wake.service projectos-wake.timer projectos-signer.service projectos-signer.timer; do
  install -m 0644 "${UNIT_SRC}/${f}" "/etc/systemd/system/${f}"
done
systemctl daemon-reload
# Timers not enabled here — founder enables after secrets are in place (see HANDOFF.md)

echo "==> resource note"
echo "Host profile: 1 vCPU / 1 GB RAM / 25 GB disk."
echo "This node is sized for wake + signer only."
echo "Dhan tape recorder: NOT installed here — footprint unmeasured; do not co-locate until measured."

echo "BOOTSTRAP OK"
echo "Next: place secrets per deploy/droplet/SECRETS.md, then enable timers per HANDOFF.md"
