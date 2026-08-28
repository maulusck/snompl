# snom-provisioner-lite (`snompl`)

Minimal, database-free auto-provisioning for Snom desk phones. One YAML fleet
file in, per-MAC XML configs out. No web app, no DB, no state; just a compiler
you point at a config.

## Install

```bash
pip install .          # or: pip install -e .  for development
```

Requires Python ≥ 3.9 and PyYAML (the only dependency).

## Quick start

```bash
snompl init            # writes a sample fleet.yaml
$EDITOR fleet.yaml     # fill in your phones
snompl generate        # -> ./output/snom/snom-<mac>.xml per device
```

## Commands

### `snompl init [-o PATH]`
Writes a sample fleet file. Refuses to overwrite an existing one.
Default: `fleet.yaml`.

### `snompl generate [-c CONFIG] [-o OUTPUT]`
Compiles a fleet into one XML file per device, named `snom-<mac>.xml`
(MAC lowercased, separators stripped, per Snom's flat-file convention).

| Flag | Default | Meaning |
|------|---------|---------|
| `-c`, `--config` | `fleet.yaml` | fleet file to read |
| `-o`, `--output` | `./output/snom` | directory to write into (created if missing) |

## Multiple setups

There's no multi-config command by design; that's a shell loop. Each setup is
its own YAML and its own output dir:

```bash
snompl generate -c office-a.yaml -o out/office-a
snompl generate -c office-b.yaml -o out/office-b

# or all at once:
for f in setups/*.yaml; do
  snompl generate -c "$f" -o "out/$(basename "$f" .yaml)"
done
```

## Fleet file format

```yaml
# Snom XML provisioning. Values apply as-is; unknown keys are silently ignored.
perm: R                          # R locked, RW or "" user-editable

settings:
  language: English
  timezone: UTC                  # Snom zone code, e.g. USA-5, ITA+1
  tone_scheme: USA
  ntp_server: pool.ntp.org
  admin_mode: "1"
  admin_mode_password: "0000"    # phone menu lock; digits 0-9
  http_user: admin               # web UI login (8.x)
  http_pass: CHANGEME
  # webserver_type: off          # disable web UI entirely; hardest lock, needs reboot
  update_policy: settings_only   # never fetch firmware

devices:
  - mac: "00-04-13-00-00-00"     # any separator; replace with real MAC
    settings:                    # optional: per-phone overrides of the globals
      timezone: USA-5
    accounts:                    # each entry becomes SIP identity idx 1, 2, ...
      - user_active: "on"
        user_name: "CHANGEME"
        user_host: pbx.example.com
        user_pass: CHANGEME
        user_realname: "CHANGEME"
  - mac: "00-04-13-00-00-01"
    accounts:
      - user_active: "on"
        user_name: "CHANGEME"
        user_host: pbx.example.com
        user_pass: CHANGEME
        user_realname: "CHANGEME"
```

**How it maps.** Everything becomes a flat setting inside one `<phone-settings>`
container, the only shape Snom's provisioning format accepts. Global
`settings` and per-device `settings` are emitted as-is; device keys override
globals on collision. Each entry under a device's `accounts` is written as an
indexed identity (`user_name idx="1"`, `user_host idx="1"`, ...); snompl assigns
the `idx` from list order, so you never number them by hand.

**Setting names are Snom's, verbatim.** There's no friendly-name layer to get
between you and the phone. Common ones: `language`, `timezone`, `tone_scheme`,
`ntp_server`, `admin_mode` / `admin_mode_password`, `update_policy`, and the
identity fields `user_active` / `user_name` / `user_host` / `user_pass` /
`user_pname` (auth user, if it differs from `user_name`) / `user_realname`. The
full list lives in Snom's docs; if a name is valid there, it's valid here. Note
that Snom silently ignores unknown setting names, so a typo is a no-op, not an
error.

**Web interface.** `http_user` / `http_pass` set the login for the phone's web
UI on 8.x firmware, separate from `admin_mode_password` (which locks only the
on-phone menu). To lock the web UI down hardest, uncomment `webserver_type: off`
to disable it entirely; the phone then has no web UI at all, and the change
needs a reboot. On the D8xx generation the web-UI credentials are instead
`webserver_admin_name` / `webserver_admin_password`, out of scope here (8.x
only), but that's the name to reach for if you add those models later.

**Permissions.** Every setting is written with the fleet's `perm` value, which
defaults to `R` (read-only / locked on the phone, the managed-fleet default).
Set the top-level `perm:` in the fleet file to change it globally: `RW` or an
empty string leaves settings user-editable on the phone.

Only `mac` is required per device (it's the filename key). A device with no
accounts still gets its settings, useful for pushing localisation to a phone
whose identity is set elsewhere.

## Firmware / updates

`update_policy: settings_only` in the sample tells the phone to apply settings
but never fetch firmware, so the phone stops probing for firmware files (no more
404 noise) while still re-reading its config. Do **not** use `never_update` for
this: that disables provisioning entirely, so the phone would stop loading your
settings too.

## Serving to phones (DHCP Option 66)

Phones fetch their config over HTTP. Point DHCP **Option 66** at the server
holding the generated files, e.g.:

```
Option 66 = http://<server>/snom
```

Snom phones request `snom-<mac>.xml` on boot, then re-check on their own
provisioning schedule. snompl no longer forces an interval; set one explicitly
via a Snom setting (e.g. `setting_server` / update cadence) if you need a
specific cadence.

### Container

```bash
podman build -t snompl:latest .
podman run -d --name snompl -p 80:80 \
  -v ./fleet.yaml:/app/fleet.yaml:ro \
  snompl:latest
```

The image mounts your `fleet.yaml` at **runtime** and generates on start, then
serves via nginx, so secrets never bake into an image layer.

## Security

The generated XML holds **cleartext SIP secrets**, which Snom's provisioning
model requires (a phone has no credentials until it's provisioned). Protect the
files with the network, not the filename.

- **Directory listing is off.** The container ships a minimal custom
  `nginx.conf` (`autoindex off`, `server_tokens off`, serves `/srv` only), so
  the server delivers `snom-<mac>.xml` but won't enumerate the directory or
  leak its version.
- **MAC filtering is deliberately not implemented.** MACs are on stickers and
  sequential within a vendor block, so filtering by requested MAC stops nobody
  while adding a parsing layer to debug at 3am. It's theatre; skipped.
- **Real controls, cheapest first:** put provisioning traffic on an isolated
  voice VLAN (the server should not be reachable from the user LAN or
  internet); add HTTPS on nginx to encrypt secrets in flight; and treat
  provisioning as a **window**: generate, let phones fetch, stop the
  container, rather than leaving secrets served 24/7.

The secret's protection is the network it rides on, not the name it hides
behind.

## Test

```bash
python test_snompl.py     # -> ok
```

## Layout

```
snom-provisioner-lite/
├── Containerfile
├── LICENSE
├── pyproject.toml
├── README.md
├── snompl.py          # the whole tool
├── test_snompl.py
└── .gitignore
```

MIT.
