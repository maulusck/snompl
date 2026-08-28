"""snompl: minimal, database-free Snom desk phone provisioner.

YAML keys are raw Snom setting names, so anything Snom accepts works here.
Account identities are listed in order; snompl assigns their idx.
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET
import yaml

DEFAULT_PERM = "R"

SAMPLE = """# perm applies to every emitted setting: R = locked, RW or "" = user-editable.
perm: R

# Global settings applied to every phone. Keys are raw Snom setting names.
settings:
  language: English
  timezone: UTC                 # add `dst:` only if the phone still logs a DST error
  tone_scheme: USA
  ntp_server: pool.ntp.org
  admin_mode: "1"
  admin_mode_password: "0000"   # digits 0-9 only; change before deploying
  update_policy: settings_only  # load settings, never fetch firmware

devices:
  - mac: "00-04-13-00-00-00"    # Snom OUI + placeholder; replace with the real MAC
    accounts:                   # each entry becomes identity idx=1, 2, 3...
      - user_active: "on"
        user_name: "CHANGEME"
        user_host: pbx.example.com
        user_pass: CHANGEME
        user_realname: "CHANGEME"
"""


def clean_mac(mac):
    """Keep hex only, lowercased (Snom flat-file convention)."""
    return "".join(c for c in mac if c in "0123456789abcdefABCDEF").lower()


def build_device(defaults, dev, perm):
    """Build the <settings> tree for one device."""
    root = ET.Element("settings")
    ps = ET.SubElement(root, "phone-settings")
    for k, v in {**defaults, **dev.get("settings", {})}.items():
        ET.SubElement(ps, k, perm=perm).text = str(v)
    for idx, acct in enumerate(dev.get("accounts", []), 1):
        for k, v in acct.items():
            ET.SubElement(ps, k, idx=str(idx), perm=perm).text = str(v)
    ET.indent(root)
    return root


def generate(config, outdir):
    with open(config) as f:
        fleet = yaml.safe_load(f) or {}
    perm = fleet.get("perm", DEFAULT_PERM)
    defaults = fleet.get("settings", {})
    devices = fleet.get("devices", [])
    os.makedirs(outdir, exist_ok=True)

    print(f"[*] Compiling {len(devices)} device(s) from {config}...")
    for i, dev in enumerate(devices):
        if not dev.get("mac"):
            sys.exit(f"[!] device {i}: missing mac")
        mac = clean_mac(dev["mac"])
        path = os.path.join(outdir, f"snom-{mac}.xml")
        ET.ElementTree(build_device(defaults, dev, perm)).write(
            path, encoding="utf-8", xml_declaration=True
        )
        print(f" [OK] snom-{mac}.xml ({len(dev.get('accounts', []))} account(s))")
    print(f"[*] Done -> {outdir}")


def main():
    parser = argparse.ArgumentParser(prog="snompl", description="Snom phone provisioner.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="write a sample fleet.yaml")
    init_p.add_argument("-o", "--output", default="fleet.yaml")

    gen_p = sub.add_parser("generate", help="compile a fleet into per-MAC XML")
    gen_p.add_argument("-c", "--config", default="fleet.yaml")
    gen_p.add_argument("-o", "--output", default="./output/snom")

    args = parser.parse_args()
    try:
        if args.cmd == "init":
            if os.path.exists(args.output):
                sys.exit(f"[!] {args.output} already exists")
            with open(args.output, "w") as f:
                f.write(SAMPLE)
            print(f"[+] wrote {args.output}")
        else:
            generate(args.config, args.output)
    except (FileNotFoundError, yaml.YAMLError) as e:
        sys.exit(f"[!] {e}")


if __name__ == "__main__":
    main()
