import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import xml.etree.ElementTree as ET
from snompl import clean_mac, build_device

assert clean_mac(" 00:04:13-AA:11:bb ") == "000413aa11bb"
assert clean_mac("0004.1300.00AA") == "0004130000aa"

root = build_device(
    {"timezone": "UTC"},
    {"accounts": [{"user_name": "101", "user_pass": "a&b<c"}]},
    "RW",
)
xml = ET.tostring(root, encoding="unicode")
assert "a&amp;b&lt;c" in xml
assert 'idx="1"' in xml
assert 'perm="RW"' in xml
assert "<timezone" in xml
print("ok")
