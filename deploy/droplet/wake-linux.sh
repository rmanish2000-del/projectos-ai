#!/usr/bin/env bash
# Linux seat wake — one loop pass.
# Engines: grok | codex | claude. Default: codex (or /etc/projectos/engine.env).
# Every real failure leaves a Drive/local note; every engine session appends FLEET-USAGE.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/projectos/projectos-ai}"
SEAT="${SEAT:-PROJECTOS}"
STATE_DIR="${STATE_DIR:-/var/lib/projectos}"
REPORTS_DIR="${REPORTS_DIR:-/mnt/gdrive/AGENT-REPORTS}"
INBOX_DIR="${INBOX_DIR:-/home/projectos/gdrive-inbox}"
SECRETS_DIR="${SECRETS_DIR:-/etc/projectos/secrets}"
ENGINE_ENV_FILE="${ENGINE_ENV_FILE:-/etc/projectos/engine.env}"
LOCK="${STATE_DIR}/wake-${SEAT}.lock"
STDERR_FILE="${STATE_DIR}/wake-${SEAT}.stderr"
LOG="${STATE_DIR}/wake-${SEAT}.log"
USAGE_LOCAL="${STATE_DIR}/wake-usage.log"

# Ensure CLIs installed under /usr/local/bin are visible (systemd PATH already includes it)
export PATH="/opt/projectos/venv/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

# Optional host-wide default (does not override explicit ENGINE= in the environment)
if [[ -z "${ENGINE:-}" && -f "${ENGINE_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a; source "${ENGINE_ENV_FILE}"; set +a
fi
ENGINE="${ENGINE:-codex}"

if [[ -n "${PROMPT_FILE:-}" ]]; then
  :
elif [[ "${SEAT}" == "CHIEF" ]]; then
  PROMPT_FILE="wake-prompt-chief.md"
else
  PROMPT_FILE="wake-prompt.md"
fi

mkdir -p "${STATE_DIR}"
cd "${REPO_ROOT}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [${SEAT}] $*" | tee -a "${LOG}"; }

write_failure() {
  local why="$*"
  local stamp name body
  stamp="$(date -u +%Y-%m-%d_%H%M)-UTC"
  name="${stamp}_${SEAT}_WAKE-FAILURE.md"
  body="WAKE FAILURE (${SEAT}): ${why}"
  if [[ -d "${REPORTS_DIR}" ]]; then
    printf '%s\n' "${body}" > "${REPORTS_DIR}/${name}" || true
  fi
  mkdir -p "${STATE_DIR}/failures"
  printf '%s\n' "${body}" > "${STATE_DIR}/failures/${name}"
  log "WAKE-FAILURE: ${why}"
}

write_usage() {
  # One line per session that reached (or attempted) an engine — same contract as wake.ps1
  local day count usage_drive
  day="$(date +%Y-%m-%d)"
  mkdir -p "${STATE_DIR}"
  echo "${day}|${SEAT}|${ENGINE}" >> "${USAGE_LOCAL}" || true
  count="$(grep -c "^${day}|${SEAT}|" "${USAGE_LOCAL}" 2>/dev/null || echo 1)"
  usage_drive="${REPORTS_DIR}/FLEET-USAGE.md"
  if [[ -d "${REPORTS_DIR}" ]]; then
    if [[ ! -f "${usage_drive}" ]]; then
      printf '%s\n' \
        "# FLEET USAGE - one line per wake session that reached an engine" \
        "" \
        "Session counts and engines are measured. Provider token counts are NOT" \
        "available to the wrapper and are never estimated here. A failed session" \
        "still counts: it consumed quota." \
        "" > "${usage_drive}" || true
    fi
    echo "${day} | ${SEAT} | engine=${ENGINE} | session #${count} today" >> "${usage_drive}" || true
  fi
}

# Source engine auth if present (never log contents)
for envf in codex.env grok.env claude.env; do
  if [[ -f "${SECRETS_DIR}/${envf}" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${SECRETS_DIR}/${envf}"; set +a
  fi
done

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

case "${ENGINE}" in
  grok|codex|claude) ;;
  *)
    write_failure "unsupported ENGINE=${ENGINE} (allowed: grok|codex|claude)"
    exit 2
    ;;
esac

if ! command -v "${ENGINE}" >/dev/null 2>&1; then
  write_failure "${ENGINE} CLI not on PATH (PATH=${PATH})"
  exit 2
fi

: > "${STDERR_FILE}"
set +e
case "${ENGINE}" in
  codex)
    cat "${prompt}" | codex exec - --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --color never \
      2>"${STDERR_FILE}"
    ;;
  grok)
    # Official xAI Grok Build CLI headless. Auth: XAI_API_KEY via grok.env — never argv.
    grok --no-auto-update --always-approve --cwd "${REPO_ROOT}" \
      -p "$(cat "${prompt}")" 2>"${STDERR_FILE}"
    ;;
  claude)
    cat "${prompt}" | claude -p 2>"${STDERR_FILE}"
    ;;
esac
rc=$?
set -e

# Count every session that reached the engine binary (success or fail)
write_usage

if [[ "${rc}" -ne 0 ]]; then
  tail=$(tail -n 40 "${STDERR_FILE}" 2>/dev/null || echo "(no stderr captured)")
  write_failure "engine exited ${rc}"$'\n'"stderr tail:"$'\n'"${tail}"
  exit 1
fi

log "OK: wake completed (engine=${ENGINE})"
exit 0
