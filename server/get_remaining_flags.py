import requests
import re

BASE_URL = "http://localhost:5000"
LOGIN_URL = f"{BASE_URL}/login"
XSS_URL = f"{BASE_URL}/xss"
CSRF_URL = f"{BASE_URL}/csrf"

s = requests.Session()
s.post(LOGIN_URL, data={'roll_no': 'SEC23001', 'password': 'compass123'})

# Task 04: XSS
r = s.get(XSS_URL)
xss_flag = re.search(r'window\.challengeFlags\.xss = decodeURIComponent\("([^"]+)"\)', r.text)
if xss_flag:
    print(f"XSS Flag (Encoded): {xss_flag.group(1)}")
    # It's URL encoded
    import urllib.parse
    print(f"XSS Flag: {urllib.parse.unquote(xss_flag.group(1))}")

# Task 05: CSRF
r = s.get(CSRF_URL)
csrf_flag = re.search(r'const csrfFlagRaw = "([^"]+)"', r.text)
if csrf_flag:
    print(f"CSRF Flag (Encoded): {csrf_flag.group(1)}")
    print(f"CSRF Flag: {urllib.parse.unquote(csrf_flag.group(1))}")
