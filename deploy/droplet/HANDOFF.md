# Droplet handoff — founder paste only

SSH into the droplet as root, then paste these lines in order:

```
curl -fsSL https://raw.githubusercontent.com/rmanish2000-del/projectos-ai/main/deploy/droplet/bootstrap.sh -o /tmp/bootstrap.sh
bash /tmp/bootstrap.sh
```

When the script prints `BOOTSTRAP OK`, place secrets exactly as listed in `deploy/droplet/SECRETS.md` (paths and modes only — no values in git), then:

```
systemctl enable --now projectos-wake.timer projectos-signer.timer
```

That is the whole install. Do not debug from the console; read `journalctl -u projectos-wake.service -n 50` if a timer fails — failures also write to Drive.
