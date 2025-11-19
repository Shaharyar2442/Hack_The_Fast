import argparse
import csv
from pathlib import Path
from datetime import datetime

from werkzeug.security import generate_password_hash

from database import DB_PATH, get_connection
from flag_cipher import encrypt_flag, hash_flag

try:
    from flag_payloads import PLAINTEXT_FLAGS
except ImportError:
    PLAINTEXT_FLAGS = []

LEADERBOARD_PLAYERS = [
    ("BTL23001", "Ada Lovelace", 1200),
    ("BTL23002", "Grace Hopper", 1180),
    ("BTL23003", "Alan Turing", 1165),
    ("BTL23004", "Annie Easley", 1130),
]

CONTRACTS = [
    ("Monarch Cyber", "Red-team readiness exercise", 85000, "VPN creds stored under vault entry v-992"),
    ("Helios Bank", "Mobile app pen test", 64000, "Data room URL: https://helios.example/deal"),
    ("Rapid Rail", "SCADA hardening review", 120000, "Flag stored in confidential appendix C"),
]

SHIPMENTS = [
    ("ZX-1001", "Red Cell Toolkit", 1),
    ("ZX-1002", "Training Badges", 0),
    ("ZX-1337", "Incident playbook", 1),
]

ADMINS = [
    ("root", "4ck-potato!"),
]

def bootstrap_schema(conn):
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                points INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT UNIQUE NOT NULL,
                code TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                flag_id INTEGER NOT NULL,
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                points INTEGER DEFAULT 0,
                UNIQUE(student_id, flag_id),
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(flag_id) REFERENCES flags(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT UNIQUE NOT NULL,
                scope TEXT NOT NULL,
                budget INTEGER DEFAULT 0,
                confidential_notes TEXT
            );

            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT UNIQUE NOT NULL,
                destination TEXT,
                delivered INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS student_stats (
                student_id INTEGER PRIMARY KEY,
                total_points INTEGER DEFAULT 0,
                total_captures INTEGER DEFAULT 0,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );
            """
        )


def ensure_flag_hash_column(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(flags)")}
    if "code_hash" not in columns:
        conn.execute("ALTER TABLE flags ADD COLUMN code_hash TEXT DEFAULT ''")


def seed_flags(conn):
    ensure_flag_hash_column(conn)
    if not PLAINTEXT_FLAGS:
        print("No plaintext flags found (flag_payloads missing). Skipping flag seeding.")
        return
    with conn:
        for category, code, description in PLAINTEXT_FLAGS:
            conn.execute(
                """
                INSERT INTO flags (category, code, code_hash, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category) DO UPDATE SET
                    code=excluded.code,
                    code_hash=excluded.code_hash,
                    description=excluded.description
                """,
                (category, encrypt_flag(code), hash_flag(code), description),
            )


def seed_leaderboard(conn):
    with conn:
        for roll_no, display_name, points in LEADERBOARD_PLAYERS:
            conn.execute(
                """
                INSERT INTO leaderboard (roll_no, display_name, points)
                VALUES (?, ?, ?)
                ON CONFLICT(roll_no) DO UPDATE SET
                    display_name=excluded.display_name,
                    points=excluded.points
                """,
                (roll_no, display_name, points),
            )


def seed_contracts(conn):
    with conn:
        for client_name, scope, budget, notes in CONTRACTS:
            conn.execute(
                """
                INSERT INTO contracts (client_name, scope, budget, confidential_notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_name) DO UPDATE SET
                    scope=excluded.scope,
                    budget=excluded.budget,
                    confidential_notes=excluded.confidential_notes
                """,
                (client_name, scope, budget, notes),
            )


def seed_shipments(conn):
    with conn:
        for tracking, destination, delivered in SHIPMENTS:
            conn.execute(
                """
                INSERT INTO shipments (tracking_number, destination, delivered)
                VALUES (?, ?, ?)
                ON CONFLICT(tracking_number) DO UPDATE SET
                    destination=excluded.destination,
                    delivered=excluded.delivered
                """,
                (tracking, destination, delivered),
            )


def seed_admins(conn):
    with conn:
        for username, password in ADMINS:
            conn.execute(
                """
                INSERT INTO admins (username, password_hash)
                VALUES (?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash=excluded.password_hash
                """,
                (username, generate_password_hash(password)),
            )


def seed_students(conn, csv_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as handle, conn:
        reader = csv.DictReader(handle)
        required_columns = {"roll_no", "name", "password", "email"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")

        for row in reader:
            conn.execute(
                """
                INSERT INTO students (roll_no, name, email, password_hash)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(roll_no) DO UPDATE SET
                    name=excluded.name,
                    email=excluded.email,
                    password_hash=excluded.password_hash
                """,
                (
                    row["roll_no"].strip(),
                    row["name"].strip(),
                    row.get("email", "").strip(),
                    generate_password_hash(row["password"].strip()),
                ),
            )


def seed_student_stats(conn):
    with conn:
        conn.execute(
            """
            INSERT INTO student_stats (student_id, total_points, total_captures)
            SELECT students.id, 0, 0
            FROM students
            LEFT JOIN student_stats ss ON ss.student_id = students.id
            WHERE ss.student_id IS NULL
            """
        )


def add_demo_feedback(conn):
    existing = conn.execute("SELECT COUNT(*) AS total FROM feedback").fetchone()["total"]
    if existing:
        return

    cursor = conn.execute("SELECT id FROM students ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return
    student_id = row["id"]
    sample_messages = [
        ("This board is perfect for testing stored XSS payloads. Try posting <script>alert('xss')</script>"),
        ("Remember: the teaching assistant account leaves hints here periodically."),
    ]
    with conn:
        for message in sample_messages:
            conn.execute(
                "INSERT INTO feedback (student_id, content, created_at) VALUES (?, ?, ?)",
                (student_id, message[0], datetime.utcnow().isoformat()),
            )


def main():
    parser = argparse.ArgumentParser(description="Initialize or update the vulnerable training database.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent / "data" / "students_sample.csv",
        help="Path to student roster CSV (columns: roll_no,name,password,email)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the existing SQLite file before seeding (use cautiously; wipes progress).",
    )
    args = parser.parse_args()

    if args.reset:
        DB_PATH.unlink(missing_ok=True)
        print("Existing database removed.")

    conn = get_connection()
    bootstrap_schema(conn)
    seed_flags(conn)
    seed_leaderboard(conn)
    seed_contracts(conn)
    seed_shipments(conn)
    seed_admins(conn)
    seed_students(conn, args.csv)
    seed_student_stats(conn)
    add_demo_feedback(conn)
    conn.close()
    print(f"Database initialized/updated at {DB_PATH}")


if __name__ == "__main__":
    main()

