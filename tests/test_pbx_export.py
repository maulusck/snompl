import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import xml.etree.ElementTree as ET
import yaml
import pbx_export
import snompl

# adversarial: YAML-bool secret/name, all-digit, specials, colon; a dup and a skip
rows = [
    {"extension": "429", "name": "on", "secret": "no"},
    {"extension": "432", "name": "12345", "secret": "0012340"},
    {"extension": "431", "name": "Anna:x", "secret": "a#b@c!d"},
    {"extension": "427", "name": "A", "secret": "shared"},
    {"extension": "428", "name": "B", "secret": "shared"},
    {"extension": "433", "name": "None", "secret": ""},
]
devices, (skipped, unbound, dupes) = pbx_export.build(rows, {"427": "00:04:13:AA:BB:01"}, "pbx.lan")
assert skipped == 1 and dupes == 1 and unbound == 4

out = yaml.safe_dump({"devices": devices}, sort_keys=False)
fleet = yaml.safe_load("perm: R\nsettings: {}\n" + out)
for dev in fleet["devices"]:
    ext = dev["accounts"][0]["user_name"]
    xml = ET.tostring(snompl.build_device({}, dev, "R"), encoding="unicode")
    if ext == "429":  # bool-ish values must survive as strings, not True/False
        assert '<user_pass idx="1" perm="R">no</user_pass>' in xml
        assert '<user_realname idx="1" perm="R">on</user_realname>' in xml
    if ext == "432":
        assert '<user_pass idx="1" perm="R">0012340</user_pass>' in xml
print("ok")
