from snompl import clean_mac, render

assert clean_mac(" 00:04:13-AA:11:bb ") == "000413aa11bb"
assert render("{{ a }}/{{ b }}", {"a": 1, "b": "x"}) == "1/x"
assert render("{{ mac }}", {"mac": "abc"}) == "abc"
print("ok")
