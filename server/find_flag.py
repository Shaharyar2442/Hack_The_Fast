import os

TARGET_FLAG = b"FLAG{Still_trying_dummy_flags}"
SEARCH_DIR = "static"

print(f"Searching for {TARGET_FLAG} in {SEARCH_DIR}...")

for root, dirs, files in os.walk(SEARCH_DIR):
    for file in files:
        path = os.path.join(root, file)
        try:
            with open(path, "rb") as f:
                content = f.read()
                if TARGET_FLAG in content:
                    print(f"FOUND in: {path}")
                elif b"Still_trying" in content:
                    print(f"PARTIAL MATCH in: {path}")
        except Exception as e:
            print(f"Error reading {path}: {e}")
