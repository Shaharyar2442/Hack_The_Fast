import sqlite3
from flag_cipher import decrypt_flag

conn = sqlite3.connect('ctf_lab.db')
head_row = conn.execute("SELECT session_data FROM session_tokens WHERE token_status = 1 LIMIT 1").fetchone()
tail_row = conn.execute("SELECT session_tail FROM session_tokens_tail WHERE token_status = 1 LIMIT 1").fetchone()

head = ""
tail = ""

if head_row:
    print(f"Head Encrypted: {head_row[0]}")
    try:
        head = decrypt_flag(head_row[0], "CSRF")
        print(f"Head Decrypted: {head}")
    except Exception as e:
        print(f"Head Error: {e}")

if tail_row:
    print(f"Tail Encrypted: {tail_row[0]}")
    try:
        tail = decrypt_flag(tail_row[0], "CSRF")
        print(f"Tail Decrypted: {tail}")
    except Exception as e:
        print(f"Tail Error: {e}")

print(f"Combined: {head}{tail}")
conn.close()
