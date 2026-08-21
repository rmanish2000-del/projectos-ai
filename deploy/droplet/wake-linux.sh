#!/usr/bin/env bash
# Linux seat wake — one loop pass. Mirrors the contract of scripts/wake.ps1:
# engine default codex; every real failure leaves a note (Drive if mounted,
# else local under /var/lib/projectos/failures so the node is never silent).
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/projectos/projectos-ai}"
SEAT="${SEAT:-PROJECTOS}"
ENGINE="${ENGINE:-codex}"
PROMPT_FILE="${PROMPT_FILE:-wake-prompt.md}"
STATE_DIR="${STATE_DIR:-/var/lib/projectos}"
REPORTS_DIR="${REPORTS_DIR:-/mnt/gdrive/AGENT-REPORTS}"
INBOX_DIR="${INBOX_DIR:-/home/projectos/gdrive-inbox}"
SECRETS_DIR="${SECRETS_DIR:-/etc/projectos/secrets}"
LOCK="${STATE_DIR}/wake-${SEAT}.lock"
STDERR_FILE="${STATE_DIR}/wake-${SEAT}.stderr"
LOG="${STATE_DIR}/wake-${SEAT}.log"

mkdir -p "${STATE_DIR}"
cd "${REPO_ROOT}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [${SEAT}] $*" | tee -a "${LOG}"; }

write_failure() {
  local why="$*"
  local stamp
  stamp="$(date -u +%Y-%m-%d_%H%M)-UTC"
  local name="${stamp}_${SEAT}_WAKE-FAILURE.md"
  local body="WAKE FAILURE (${SEAT}): ${why}"
  if [[ -d "${REPORTS_DIR}" ]]; then
    printf '%s\n' "${body}" > "${REPORTS_DIR}/${name}" || true
  fi
  mkdir -p "${STATE_DIR}/failures"
  printf '%s\n' "${body}" > "${STATE_DIR}/failures/${name}"
  log "WAKE-FAILURE: ${why}"
}

# Source engine auth if present (never log contents)
if [[ -f "${SECRETS_DIR}/codex.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "${SECRETS_DIR}/codex.env"; set +a
fi

if [[ -f "${LOCK}" ]]; then
  oldpid=$(awk -F= '/^pid=/{print $2}' "${LOCK}" || true)
  if [[ -n "${oldpid}" ]] && kill -0 "${oldpid}" 2>/dev/null; then
    log "SKIP: seat already running (pid ${oldpid})"
    exit 0
  fi
  rm -f "${LOCK}"
fi
echo "pid=$$" > "${LOCK}"
trap 'rm -f "${LOCK}"' EXIT

prompt="${REPO_ROOT}/${PROMPT_FILE}"
if [[ ! -f "${prompt}" ]]; then
  write_failure "${PROMPT_FILE} missing at ${prompt} (REPO_ROOT=${REPO_ROOT})"
  exit 2
fi

if ! command -v "${ENGINE}" >/dev/null 2>&1; then
  write_failure "${ENGINE} CLI not on PATH"
  exit 2
fi

: > "${STDERR_FILE}"
set +e
if [[ "${ENGINE}" == "codex" ]]; then
  # workspace-write invokes bwrap networking and fails on this droplet with
  # RTM_NEWADDR. This wrapper is already isolated to the dedicated fleet host.
  cat "${prompt}" | codex exec - --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --color never \
    2>"${STDERR_FILE}"
else
  cat "${prompt}" | claude -p 2>"${STDERR_FILE}"
fi
rc=$?
set -e

if [[ "${rc}" -ne 0 ]]; then
  tail=$(tail -n 40 "${STDERR_FILE}" 2>/dev/null || echo "(no stderr captured)")
  write_failure "engine exited ${rc}"$'\n'"stderr tail:"$'\n'"${tail}"
  exit 1
fi

log "OK: wake completed (engine=${ENGINE})"
exit 0
