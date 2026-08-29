# snom-provisioner-lite (snompl)

Minimal, database-free provisioning for Snom desk phones. One YAML fleet file
in, one XML file per phone out. No web application, no database, no persistent
state: a compiler you point at a configuration, with an optional exporter that
builds the fleet from an Asterisk PBX.

## Firmware support

snompl targets Snom 8.x firmware, and the settings in the sample fleet are
verified against it. It is not restricted to 8.x: because it emits Snom setting
names verbatim rather than mapping them to its own vocabulary, any setting from
the Snom documentation can be added to a fleet and is written as given. Newer
generations are supported the same way, by using their setting names directly.
For example, the 8.x web-interface login is `http_user` / `http_pass`, while the
D8xx generation uses `webserver_admin_name` / `webserver_admin_password`.

Setting reference: https://service.snom.com/spaces/wiki/pages/234339765/Auto+Provisioning

## Installation

```bash
pip install snompl          # compiler: init, generate
pip install snompl[pbx]     # adds the Asterisk exporter (PyMySQL)
```

Requires Python 3.9 or later. From a source checkout, `python ./snompl.py
<command>` is equivalent to the installed `snompl` command.

## Workflow

```bash
snompl init                        > fleet.yaml
snompl export --macs macs.csv     >> fleet.yaml     # optional, on the PBX
snompl generate                                     # -> ./output/snom/snom-<mac>.xml
```

`init` writes the global settings, `export` appends devices read from the PBX,
and `generate` compiles the fleet into one XML file per phone. For a small
number of phones, omit `export` and list the devices in `fleet.yaml` directly.

## Commands

| Command | Purpose |
|---------|---------|
| `snompl init [-o PATH]` | Write a sample fleet file (globals only). Refuses to overwrite. Default `fleet.yaml`. |
| `snompl export [OPTIONS]` | Read the local Asterisk database and write a devices block to standard output. See [Building a fleet from Asterisk](#building-a-fleet-from-asterisk). |
| `snompl generate [-c CONFIG] [-o OUTPUT]` | Compile a fleet into per-MAC XML. Defaults: `fleet.yaml`, `./output/snom`. |
| `snompl --version` | Print the version. |

An unrecognised argument prints usage and exits without side effects.

## Multiple sites

There is no multi-configuration command; each site is its own fleet file and
output directory:

```bash
for f in setups/*.yaml; do
  snompl generate -c "$f" -o "out/$(basename "$f" .yaml)"
done
```

## Fleet file format

```yaml
# Snom XML provisioning. Values apply as-is; unknown keys are silently ignored.
# Setting reference: https://service.snom.com/spaces/wiki/pages/234339765/Auto+Provisioning
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
  webserver_type: https          # web UI over HTTPS; needs reboot (off = disable entirely)
  update_policy: settings_only   # never fetch firmware

devices:
  - mac: "00-04-13-00-00-00"     # any separator; replace with the real MAC
    settings:                    # optional per-phone overrides
      timezone: USA-5
    accounts:                    # each entry becomes SIP identity idx 1, 2, ...
      - user_active: "on"
        user_name: "CHANGEME"
        user_host: pbx.example.com
        user_pass: CHANGEME
        user_realname: "CHANGEME"
```

`snompl init` omits the `devices:` block so the exporter can append one; add it
manually when editing by hand.

**Structure.** Every value becomes a flat setting inside a single
`<phone-settings>` element, the only container Snom's provisioning format
accepts. Global `settings` and per-device `settings` are written as given, and
per-device keys override globals. Each entry under `accounts` becomes an indexed
SIP identity (`user_name idx="1"`, and so on), numbered from list order.

**Setting names.** Names are Snom's own, written verbatim; there is no
translation layer. Commonly used: `language`, `timezone`, `tone_scheme`,
`ntp_server`, `admin_mode`, `admin_mode_password`, `update_policy`, and the
identity fields `user_active`, `user_name`, `user_host`, `user_pass`,
`user_pname` (authentication user, when it differs from `user_name`), and
`user_realname`. Unknown names are ignored by the phone, so a typo is a no-op
rather than an error.

**Web interface.** `http_user` and `http_pass` set the phone's web login on 8.x,
independent of `admin_mode_password`, which locks only the on-phone menu.
`webserver_type: https` serves the web interface over HTTPS, self-signed until a
certificate is provisioned; `off` disables it entirely. Either change requires a
reboot.

**Permissions.** Each setting is written with the fleet's `perm` value, `R` by
default (read-only on the phone). Set the top-level `perm` to change it
globally; `RW` or an empty string leaves settings user-editable.

Only `mac` is required per device. A device with no accounts still receives the
global settings.

## Building a fleet from Asterisk

`snompl export` reads the local Asterisk database (`users` joined to `sip` on
`keyword='secret'`), optionally binds each extension to a MAC address, and
writes a devices block. It requires `pip install snompl[pbx]` and connects over
the local MariaDB Unix socket as the current operating-system user, so no
credentials are stored in the tool.

```
snompl export [--macs CSV] [--host HOST] [--db NAME] [--socket PATH]
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--macs` | none | `ext,mac` file, or `-` to read from standard input. Unlisted extensions receive the placeholder MAC `00-04-13-00-00-00`. |
| `--host` | server FQDN | SIP registrar host. |
| `--db` | `asterisk` | Database name. |
| `--socket` | `/var/run/mysqld/mysqld.sock` | MariaDB Unix socket. |

`grep 00-04-13-00-00-00 fleet.yaml` lists the phones still awaiting a MAC.
Extensions without a secret are reported and skipped, since a phone without a
secret cannot register. Shared secrets are reported; Asterisk installations
frequently reuse a default secret, which should be rotated before provisioning.

### Running from another host

The exporter reads the PBX database directly and is intended to run on the PBX.
There is no remote-database option: to run it from a workstation, invoke the
command over SSH so it executes on the PBX and only the result is returned.

```bash
ssh pbx.example.com 'snompl export --macs -' < macs.csv >> fleet.yaml
```

If the database cannot be reached, the tool reports the cause and the corrective
action.

## Serving to phones

Phones fetch their configuration over HTTP. Point DHCP option 66 at the
directory holding the generated files:

```
Option 66 = http://<server>/snom
```

Each phone requests `snom-<mac>.xml` at boot and re-checks on its own schedule.

### FreePBX host

Symlink the generated directory into the FreePBX document root and let Apache
force the interface to HTTPS while serving `/snom/` over plain HTTP, since phones
have no certificate trust before they are provisioned:

```bash
ln -s /path/to/output/snom /var/www/html/snom
```

```apache
<VirtualHost *:80>
    DocumentRoot /var/www/html

    <Directory /var/www/html>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    # Redirect everything to HTTPS except /snom/
    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/snom/(.*)$ [NC]
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</VirtualHost>
```

### Container

```bash
podman build -t snompl:latest .
podman run -d --name snompl -p 80:80 \
  -v ./fleet.yaml:/app/fleet.yaml:ro \
  snompl:latest
```

The image mounts `fleet.yaml` at runtime and generates on start, so secrets are
never written into an image layer.

## Security

The generated XML contains cleartext SIP secrets, which Snom's provisioning
model requires: a phone holds no credentials until it is provisioned. Protect
the files at the network layer rather than by obscurity.

- Directory listing is disabled. The container's nginx configuration serves the
  provisioning directory only, without indexing or a version banner.
- MAC-based filtering is not implemented. MAC addresses are printed on the
  devices and are sequential within a vendor block, so filtering requests by MAC
  provides no meaningful protection.
- Place provisioning traffic on an isolated voice VLAN that is unreachable from
  the user network, and serve over HTTPS to encrypt secrets in transit.

The strongest measure is to expose the files only while provisioning is in
progress: generate them when a provisioning run is due, and remove them once the
phones have fetched, so the secrets are never reachable outside that window. In
the container this means running it only for the duration of the run. On a
persistent web server, such as the FreePBX host above, create the symlink (or
copy the files into place) for the window and remove it afterwards, rather than
leaving the provisioning directory exposed continuously.

The security of the secrets rests on the network they traverse and the time they
are exposed, not on the file names.

## Testing

```bash
python tests/test_snompl.py
python tests/test_pbx_export.py
```

## Layout

```
snom-provisioner-lite/
├── snompl.py            compiler: init, generate, CLI router
├── pbx_export.py        Asterisk exporter (optional PyMySQL)
├── tests/
├── pyproject.toml
├── Containerfile
├── README.md
├── LICENSE
└── .github/workflows/publish.yml
```

Licensed under the MIT License.
