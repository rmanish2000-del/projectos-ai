# Droplet handoff — founder paste only

Securely copy `bootstrap.sh` and the four founder-held files listed in
`SECRETS.md` to the droplet. SSH in as root, put the secret files at their
documented paths, then run:

```
bash /tmp/bootstrap.sh
```

When the script prints `BOOTSTRAP OK`, enable the timers:

```
systemctl enable --now projectos-wake.timer projectos-signer.timer projectos-outreach-watch.timer
```

Bootstrap creates `/opt/projectos/venv`, clones through the deploy key, installs
and starts both Drive mounts, installs the keyring copy, and installs all units.
Do not debug from the console; read `journalctl -u projectos-wake.service -n 50`
if a timer fails — failures also write to Drive.
