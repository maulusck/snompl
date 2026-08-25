# snom-provisioner-lite (`snompl`)

Minimal, database-free auto-provisioning for Snom desk phones (710 and
compatible). One YAML fleet file in, per-MAC XML configs out. No web app, no
DB, no state — just a compiler you point at a config.

## Install

```bash
pip install .          # or: pip install -e .  for development
```

Requires Python ≥ 3.8 and PyYAML (the only dependency).

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
(MAC lowercased, separators stripped — Snom's flat-file convention).

| Flag | Default | Meaning |
|------|---------|---------|
| `-c`, `--config` | `fleet.yaml` | fleet file to read |
| `-o`, `--output` | `./output/snom` | directory to write into (created if missing) |

## Multiple setups

There's no multi-config command by design — that's a shell loop. Each setup is
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
global:                       # applied to every device
  pbx: pbx.internal.lan
  ntp: pool.ntp.org
  admin_pin: SecureAdminPin123
  logo: http://pbx.internal.lan/branding/logo.bmp

devices:
  - mac: "00-04-13-AA-11-BB"  # any separator style; normalized for you
    ext: "101"
    secret: SuperSecretSIP1
    name: Reception Desk
  - mac: "00:04:13:CC:22:DD"
    ext: "102"
    secret: SuperSecretSIP2
    name: Sales
```

Required per device: `mac`, `ext`, `secret`, `name`. A missing field lists
every gap for that device and stops.

Global values fill `{{ pbx }}`, `{{ ntp }}`, `{{ admin_pin }}`, `{{ logo }}`.
Device values fill `{{ mac }}`, `{{ ext }}`, `{{ secret }}`, `{{ name }}`.
Device keys override globals if they collide.

The XML template is inlined in `snompl.py` (constant `DEVICE_XML`). Edit it
there if your phones need different settings.

## Serving to phones (DHCP Option 66)

Phones fetch their config over HTTP. Point DHCP **Option 66** at the server
holding the generated files, e.g.:

```
Option 66 = http://<server>/snom
```

Snom phones request `snom-<mac>.xml` on boot and re-check every 1440 minutes
(set in the template).

### Container

```bash
podman build -t snompl:latest .
podman run -d --name snompl -p 80:80 \
  -v ./fleet.yaml:/app/fleet.yaml:ro \
  snompl:latest
```

The image mounts your `fleet.yaml` at **runtime** and generates on start, then
serves via nginx — secrets never bake into an image layer.

## Security

The generated XML holds **cleartext SIP secrets** — Snom's provisioning model
requires it (a phone has no credentials until it's provisioned). Protect the
files with the network, not the filename.

- **Directory listing is off** — the container ships a minimal custom
  `nginx.conf` (`autoindex off`, `server_tokens off`, serves `/srv` only), so
  the server delivers `snom-<mac>.xml` but won't enumerate the directory or
  leak its version.
- **MAC filtering is deliberately not implemented.** MACs are on stickers and
  sequential within a vendor block — filtering by requested MAC stops nobody
  and adds a parsing layer to debug at 3am. It's theatre; skipped.
- **Real controls, cheapest first:** put provisioning traffic on an isolated
  voice VLAN (the server should not be reachable from the user LAN or
  internet); add HTTPS on nginx to encrypt secrets in flight; and treat
  provisioning as a **window** — generate, let phones fetch, stop the
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
├── pyproject.toml
├── README.md
├── snompl.py          # the whole tool (~90 lines)
└── test_snompl.py
```

MIT.
