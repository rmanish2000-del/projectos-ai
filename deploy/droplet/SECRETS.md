# Secrets layout (no values — ever)

All secrets live under `/etc/projectos/secrets/`, owned by `root:projectos` with
mode `0750`; each file is `projectos:projectos` mode `0600`. Nothing in this
repository, nothing in AGENT-REPORTS, nothing in unit Environment= lines.

| File | Purpose | Rotation |
|------|---------|----------|
| `/etc/projectos/secrets/codex.env` | Codex/OpenAI auth for headless engine (env file sourced by wake) | Rotate provider key; rewrite file; `systemctl restart projectos-wake.service` not required (next timer pick-up) |
| `/etc/projectos/secrets/k1` | Inbox HMAC signing key material for auto-signer | Generate new k1 offline; replace file; next signer sweep uses it |
| `/etc/projectos/secrets/gdrive-sa.json` | Service-account JSON for Drive write (reports / failures) if rclone/gdrive path is used | Rotate SA key in Google Cloud; replace JSON; no repo change |
| `/etc/projectos/secrets/github-deploy-key` | Read/write SSH deploy key for the private repository | Rotate in GitHub and replace before bootstrap/update |

`codex.env` must export `CODEX_API_KEY`; `OPENAI_API_KEY` alone is not accepted
by the headless Codex CLI and results in `401 Missing bearer`.

Bootstrap copies `/etc/projectos/secrets/k1` to the runtime keyring path
`/home/projectos/.projectos/inbox.key` with mode `0600`.

**Rules**
- Founder places files before bootstrap; bootstrap never creates secret values.
- `chmod 600` / `chown projectos:projectos` on each file.
- Never pass secrets via CLI argv (visible in `ps`).
- Never commit, paste into issues, or put in reports.
