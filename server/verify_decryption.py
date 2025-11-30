import sqlite3
from flag_cipher import decrypt_flag

conn = sqlite3.connect('ctf_lab.db')
cursor = conn.execute("SELECT auth_token FROM access_keys WHERE status_code = 200 LIMIT 1")
row = cursor.fetchone()
if row:
    encrypted_flag = row[0]
    print(f"Encrypted Flag: {encrypted_flag}")
    try:
        decrypted = decrypt_flag(encrypted_flag, "SQLI_BLIND")
        print(f"Decrypted Flag: {decrypted}")
    except Exception as e:
        print(f"Decryption Error: {e}")
else:
    print("No flag found in DB")
conn.close()
