"""snompl export: read Asterisk extensions, emit a snompl `devices:` block.

Runs where the asterisk DB is local (the PBX). PyMySQL is imported lazily so
the rest of snompl needs no database driver. This module has no entry point of
its own; reach it through `snompl export`.
"""
import csv
import os
import socket
import sys

try:
    import yaml
except ImportError:
    sys.exit("[!] PyYAML not installed: pip install PyYAML")

PLACEHOLDER_MAC = "00-04-13-00-00-00"

QUERY = (
    "SELECT u.extension, u.name, s.data AS secret "
    "FROM users u JOIN sip s ON s.id = u.extension AND s.keyword = 'secret' "
    "ORDER BY u.extension"
)


def load_macs(path):
    f = sys.stdin if path == "-" else open(path, newline="")
    try:
        return {e.strip(): m.strip() for e, m in csv.reader(f) if e.strip()}
    finally:
        if f is not sys.stdin:
            f.close()


def fetch(db):
    try:
        import pymysql
    except ImportError:
        sys.exit("[!] snompl export needs a MySQL driver: pip install snompl[pbx]")
    try:
        con = pymysql.connect(read_default_file=os.path.expanduser("~/.my.cnf"),
                              database=db, cursorclass=pymysql.cursors.DictCursor)
    except pymysql.Error as e:
        sys.exit(
            f"[!] cannot reach the '{db}' database on localhost: {e}\n"
            "    snompl export reads the PBX database directly, so run it ON the PBX.\n"
            "    From elsewhere, run the whole command over SSH instead:\n"
            "        ssh pbx.example.com 'snompl export --macs -' < macs.csv >> fleet.yaml"
        )
    try:
        with con.cursor() as cur:
            cur.execute(QUERY)
            return cur.fetchall()
    finally:
        con.close()


def build(rows, macs, host):
    seen, devices = {}, []
    skipped = unbound = dupes = 0
    for r in rows:
        ext, secret = str(r["extension"]), r["secret"]
        if not secret:
            print(f"[skip] ext {ext}: no secret", file=sys.stderr)
            skipped += 1
            continue
        if secret in seen:
            print(f"[warn] ext {ext}: secret shared with ext {seen[secret]}", file=sys.stderr)
            dupes += 1
        else:
            seen[secret] = ext
        mac = macs.get(ext, PLACEHOLDER_MAC)
        if mac == PLACEHOLDER_MAC:
            unbound += 1
        devices.append({
            "mac": mac,
            "accounts": [{
                "user_active": "on",
                "user_name": ext,
                "user_host": host,
                "user_pass": secret,
                "user_realname": r["name"] or ext,
            }],
        })
    return devices, (skipped, unbound, dupes)


def run(args):
    macs = load_macs(args.macs) if args.macs else {}
    rows = fetch(args.db)
    devices, (skipped, unbound, dupes) = build(rows, macs, args.host or socket.getfqdn())
    yaml.safe_dump({"devices": devices}, sys.stdout, sort_keys=False, default_flow_style=False)
    print(f"[*] {len(rows)} ext, {skipped} skipped, {unbound} unbound, {dupes} shared-secret",
          file=sys.stderr)
