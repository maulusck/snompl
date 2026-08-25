"""snompl: minimal, database-free Snom desk phone provisioner."""
import argparse
import os
import sys
import yaml

# ponytail: template inlined. add a --template flag if fleets ever need custom XML.
DEVICE_XML = """<?xml version="1.0" encoding="utf-8"?>
<settings>
  <phone-settings>
    <admin_mode perm="R">1</admin_mode>
    <admin_password perm="RW">{{ admin_pin }}</admin_password>
    <ntp_server perm="R">{{ ntp }}</ntp_server>
    <image_logo perm="R">{{ logo }}</image_logo>
    <display_name perm="R">{{ name }}</display_name>
    <lldp_enable perm="R">off</lldp_enable>
    <auto_provision_timer perm="R">1440</auto_provision_timer>
    <auto_provision_on_boot perm="R">on</auto_provision_on_boot>
  </phone-settings>
  <accounts>
    <account idx="1" perm="RW">
      <server perm="R">{{ pbx }}</server>
      <user_name perm="R">{{ ext }}</user_name>
      <account_name perm="R">{{ ext }} - {{ name }}</account_name>
      <pass_name perm="R">{{ secret }}</pass_name>
    </account>
  </accounts>
</settings>
"""

SAMPLE = """global:
  pbx: pbx.internal.lan
  ntp: pool.ntp.org
  admin_pin: SecureAdminPin123
  logo: http://pbx.internal.lan/branding/logo.bmp

devices:
  - mac: "00-04-13-AA-11-BB"
    ext: "101"
    secret: SuperSecretSIP1
    name: Reception Desk
"""

REQUIRED = ("mac", "ext", "secret", "name")


def clean_mac(mac):
    """Snom flat-file convention: lowercase hex, no separators."""
    return mac.replace(":", "").replace("-", "").strip().lower()


def render(tmpl, ctx):
    for k, v in ctx.items():
        tmpl = tmpl.replace(f"{{{{ {k} }}}}", str(v))
    return tmpl


def generate(config, outdir):
    with open(config) as f:  # raises FileNotFoundError -> caught in main()
        fleet = yaml.safe_load(f) or {}
    glob = fleet.get("global", {})
    devices = fleet.get("devices", [])
    os.makedirs(outdir, exist_ok=True)

    print(f"[*] Compiling {len(devices)} device(s) from {config}...")
    for i, dev in enumerate(devices):
        missing = [k for k in REQUIRED if not dev.get(k)]
        if missing:
            sys.exit(f"[!] device {i}: missing {', '.join(missing)}")
        mac = clean_mac(dev["mac"])
        path = os.path.join(outdir, f"snom-{mac}.xml")
        with open(path, "w") as f:
            f.write(render(DEVICE_XML, {**glob, **dev, "mac": mac}))
        print(f" [OK] snom-{mac}.xml (ext {dev['ext']})")
    print(f"[*] Done -> {outdir}")


def main():
    p = argparse.ArgumentParser(prog="snompl", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="write a sample fleet.yaml")
    i.add_argument("-o", "--output", default="fleet.yaml")

    g = sub.add_parser("generate", help="compile a fleet into per-MAC XML")
    g.add_argument("-c", "--config", default="fleet.yaml")
    g.add_argument("-o", "--output", default="./output/snom")

    a = p.parse_args()
    try:
        if a.cmd == "init":
            if os.path.exists(a.output):
                sys.exit(f"[!] {a.output} already exists")
            with open(a.output, "w") as f:
                f.write(SAMPLE)
            print(f"[+] wrote {a.output}")
        else:
            generate(a.config, a.output)
    except (FileNotFoundError, yaml.YAMLError) as e:
        sys.exit(f"[!] {e}")


if __name__ == "__main__":
    main()
