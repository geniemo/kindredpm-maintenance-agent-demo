import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "maintenance.db"

TIME_SLOTS = [
    "오전 10시",
    "오전 11시",
    "오후 1시",
    "오후 2시",
    "오후 3시",
    "오후 4시",
]


def get_connection():
    """SQLite DB 커넥션을 반환합니다."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """DB 초기화: 테이블 생성 및 향후 7일치 슬롯 시딩."""
    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS available_slots (
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            is_available INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (date, time_slot)
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repairs (
            ticket_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            issue_description TEXT NOT NULL,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled'
        )
    """
    )

    _seed_slots(conn)
    conn.close()


def _seed_slots(conn):
    """오늘 기준 향후 7일치 슬롯을 생성합니다. 이미 존재하는 슬롯은 건드리지 않습니다."""
    today = date.today()
    for day_offset in range(1, 8):
        d = (today + timedelta(days=day_offset)).isoformat()
        for slot in TIME_SLOTS:
            conn.execute(
                "INSERT OR IGNORE INTO available_slots (date, time_slot, is_available) VALUES (?, ?, 1)",
                (d, slot),
            )
    conn.commit()


def get_available_slots(target_date: str) -> list[str]:
    """특정 날짜의 빈 시간대 목록을 반환합니다."""
    conn = get_connection()
    _seed_slots(conn)
    cursor = conn.execute(
        "SELECT time_slot FROM available_slots WHERE date = ? AND is_available = 1 ORDER BY time_slot",
        (target_date,),
    )
    slots = [row[0] for row in cursor.fetchall()]
    conn.close()
    return slots


def book_slot(target_date: str, time_slot: str) -> bool:
    """시간대를 예약합니다. 성공 시 True, 이미 예약된 경우 False."""
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE available_slots SET is_available = 0 WHERE date = ? AND time_slot = ? AND is_available = 1",
        (target_date, time_slot),
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def restore_slot(target_date: str, time_slot: str):
    """취소된 예약의 시간대를 복구합니다."""
    conn = get_connection()
    conn.execute(
        "UPDATE available_slots SET is_available = 1 WHERE date = ? AND time_slot = ?",
        (target_date, time_slot),
    )
    conn.commit()
    conn.close()


def generate_ticket_id(target_date: str) -> str:
    """KPM-YYYYMMDD-NNN 형식의 티켓 번호를 생성합니다."""
    date_part = target_date.replace("-", "")
    conn = get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM repairs WHERE date = ?",
        (target_date,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return f"KPM-{date_part}-{count + 1:03d}"


def create_repair(
    ticket_id: str,
    name: str,
    address: str,
    target_date: str,
    time_slot: str,
    issue_type: str,
    issue_description: str,
    email: str | None = None,
) -> dict:
    """수리 예약 레코드를 생성합니다."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO repairs (ticket_id, name, address, date, time_slot, issue_type, issue_description, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ticket_id,
            name,
            address,
            target_date,
            time_slot,
            issue_type,
            issue_description,
            email,
        ),
    )
    conn.commit()
    conn.close()
    return {
        "ticket_id": ticket_id,
        "name": name,
        "address": address,
        "date": target_date,
        "time_slot": time_slot,
        "issue_type": issue_type,
        "issue_description": issue_description,
        "email": email,
        "status": "scheduled",
    }


def get_repair(ticket_id: str) -> dict | None:
    """티켓 번호로 예약 정보를 조회합니다."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM repairs WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def cancel_repair_record(ticket_id: str) -> dict:
    """예약을 취소하고 슬롯을 복구합니다."""
    repair = get_repair(ticket_id)
    if not repair:
        return {"error": "해당 티켓을 찾을 수 없습니다"}
    if repair["status"] == "cancelled":
        return {"error": "이미 취소된 예약입니다"}

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE repairs SET status = 'cancelled' WHERE ticket_id = ?",
            (ticket_id,),
        )
        conn.execute(
            "UPDATE available_slots SET is_available = 1 WHERE date = ? AND time_slot = ?",
            (repair["date"], repair["time_slot"]),
        )
        conn.commit()
    finally:
        conn.close()

    repair["status"] = "cancelled"
    return repair
