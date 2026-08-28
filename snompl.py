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

SAMPLE = """# Snom XML provisioning. Values apply as-is; unknown keys are silently ignored.
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
    accounts:                    # each entry becomes SIP identity idx 1, 2, ...
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
