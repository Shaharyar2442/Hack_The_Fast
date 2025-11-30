import re

with open("static/img/Bomb.png", "rb") as f:
    content = f.read()
    # Look for strings starting with FLAG
    # Simple strings check
    strings = re.findall(b"[A-Za-z0-9_{}]{5,}", content)
    for s in strings:
        if b"FLAG" in s:
            print(f"Found potential flag: {s}")
