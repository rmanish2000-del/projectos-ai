# Secrets layout (no values — ever)

All secrets live under `/etc/projectos/secrets/`, owned by `root:projectos` with
mode `0750`; each file is `projectos:projectos` mode `0600`. Nothing in this
repository, nothing in AGENT-REPORTS, nothing in unit Environment= lines.

| File | Purpose | Rotation |
|------|---------|----------|
| `/etc/projectos/secrets/codex.env` | Codex/OpenAI auth for headless engine (env file sourced by wake) | Rotate provider key; rewrite file; next timer pick-up |
| `/etc/projectos/secrets/grok.env` | xAI Grok CLI auth — must export `XAI_API_KEY` (console.x.ai) | Rotate at console.x.ai; replace file |
| `/etc/projectos/secrets/claude.env` | Optional Claude CLI auth if not already on the host keyring | Rotate provider key; replace file |
| `/etc/projectos/secrets/k1` | Inbox HMAC signing key material for auto-signer | Generate new k1 offline; replace file |
| `/etc/projectos/secrets/gdrive-sa.json` | Service-account JSON for Drive write | Rotate SA key in Google Cloud; replace JSON |
| `/etc/projectos/secrets/github-deploy-key` | Read/write SSH deploy key for the private repository | Rotate in GitHub and replace |

`codex.env` must export `CODEX_API_KEY`; `OPENAI_API_KEY` alone is not accepted
by the headless Codex CLI and results in `401 Missing bearer`.

`grok.env` must export `XAI_API_KEY`. The official CLI (`grok -p`) uses this for
headless / CI runs. Install CLI on the node: `curl -fsSL https://x.ai/cli/install.sh | bash`
(or `npm i -g @xai-official/grok`). Do not put the key in the unit file or in git.

Bootstrap copies `/etc/projectos/secrets/k1` to the runtime keyring path
`/home/projectos/.projectos/inbox.key` with mode `0600`.

**Rules**
- Founder places files before bootstrap; bootstrap never creates secret values.
- `chmod 600` / `chown projectos:projectos` on each file.
- Never pass secrets via CLI argv (visible in `ps`).
- Never commit, paste into issues, or put in reports.
