import os
import smtplib
from email.mime.text import MIMEText

from .db import (
    book_slot,
    cancel_repair_record,
    create_repair,
    generate_ticket_id,
    get_available_slots,
    get_repair,
    init_db,
)

init_db()

QUICK_FIX_DATA = {
    "sink_leak": (
        "1. 싱크대 아래쪽에 있는 지수밸브(수도 잠금 장치)를 시계 방향으로 돌려서 잠가주세요.\n"
        "2. 누수 부위 아래에 양동이나 대야를 받쳐 물을 받아주세요.\n"
        "3. 배관 주변을 수건으로 감싸 물이 튀는 것을 방지해주세요.\n"
        "4. 주변에 전기 콘센트가 있다면 물이 닿지 않도록 주의해주세요."
    ),
    "toilet_clog": (
        "1. 변기 물을 더 이상 내리지 마세요. 역류할 수 있습니다.\n"
        "2. 변기 주변 바닥에 신문지나 수건을 깔아 오염을 방지해주세요.\n"
        "3. 뚫어뻥(플런저)이 있다면, 변기 배수구에 밀착시킨 후 위아래로 힘차게 펌핑해주세요.\n"
        "4. 뚫어뻥이 없다면, 따뜻한 물(뜨겁지 않은)에 주방세제를 섞어 변기에 부은 후 10~15분 기다려주세요.\n"
        "5. 위 방법으로 해결되지 않으면 변기 사용을 중단하고 수리 예약을 진행해주세요."
    ),
    "boiler_issue": (
        "1. 보일러 전원이 켜져 있는지 확인해주세요.\n"
        "2. 보일러 조절기에서 희망 온도가 적절히 설정되어 있는지 확인해주세요.\n"
        "3. 보일러 본체의 수압 게이지를 확인해주세요. 정상 범위는 1.0~1.5bar입니다.\n"
        "4. 보일러에 에러 코드가 표시되어 있다면, 전원을 끄고 30초 후 다시 켜 보세요(리셋).\n"
        "5. 가스 냄새가 나거나 이상한 소리가 들리면, 즉시 보일러를 끄고 창문을 열어 환기해주세요."
    ),
    "door_lock_issue": (
        "1. 도어록의 배터리를 교체해보세요. 대부분의 디지털 도어록은 AA 또는 9V 건전지를 사용합니다.\n"
        "2. 배터리 교체 후에도 작동하지 않으면, 도어록 뒷면의 리셋 버튼을 5초간 눌러주세요.\n"
        "3. 비상 열쇠(기계식 열쇠)가 있다면 이를 사용해 출입하세요.\n"
        "4. 잠겨서 출입이 불가한 경우, KindredPM 긴급 연락처(02-1234-5678)로 즉시 연락해주세요."
    ),
    "mold_issue": (
        "1. 곰팡이가 발생한 공간의 창문을 열어 환기해주세요.\n"
        "2. 곰팡이 부위를 직접 만지지 마시고, 만지실 경우 반드시 고무장갑을 착용해주세요.\n"
        "3. 곰팡이 범위가 작다면(A4 용지 크기 이하), 물과 중성세제를 섞어 부드러운 천으로 닦아주세요.\n"
        "4. 결로(물방울 맺힘)가 원인이라면, 가구를 벽에서 5~10cm 띄워 공기 순환을 확보해주세요.\n"
        "5. 곰팡이가 넓은 범위에 퍼져 있거나 반복적으로 발생한다면, 수리 예약을 진행해주세요."
    ),
}


def provide_quick_fix(issue_type: str) -> dict:
    """응급조치 방법을 안내합니다. issue_type에 해당하는 응급조치 절차를 반환합니다."""
    if issue_type in QUICK_FIX_DATA:
        return {
            "instructions": QUICK_FIX_DATA[issue_type],
            "guide": "위 응급조치를 모든 단계 빠짐없이 번호 목록으로 안내하세요.",
        }
    return {"error": f"지원하지 않는 문제 유형입니다: {issue_type}"}


def check_available_slots(date: str, issue_type: str) -> dict:
    """특정 날짜의 예약 가능한 시간대를 조회합니다."""
    slots = get_available_slots(date)
    if not slots:
        return {
            "date": date,
            "available_slots": [],
            "message": f"{date}에는 예약 가능한 시간대가 없습니다.",
        }
    return {"date": date, "available_slots": slots}


def schedule_repair(
    name: str,
    address: str,
    date: str,
    time_slot: str,
    issue_type: str,
    issue_description: str,
    email: str,
) -> dict:
    """수리 일정을 예약합니다. 빈 시간대 검증 후 예약을 생성하고 티켓 번호를 발행합니다."""
    if not book_slot(date, time_slot):
        return {"error": f"{date} {time_slot}은(는) 이미 예약된 시간대입니다."}

    ticket_id = generate_ticket_id(date)
    repair = create_repair(
        ticket_id=ticket_id,
        name=name,
        address=address,
        target_date=date,
        time_slot=time_slot,
        issue_type=issue_type,
        issue_description=issue_description,
        email=email,
    )
    notification = _send_notification(email, ticket_id, "scheduled")
    repair["message"] = (
        f"{name}님, {date} {time_slot}에 수리 기사가 방문할 예정입니다. 티켓 번호: {ticket_id}"
    )
    repair["email_status"] = notification.get("status", "skipped")
    return repair


def check_repair_status(ticket_id: str) -> dict:
    """티켓 번호로 수리 예약 상태를 조회합니다."""
    repair = get_repair(ticket_id)
    if not repair:
        return {"error": f"티켓 번호 {ticket_id}에 해당하는 예약을 찾을 수 없습니다."}
    return repair


def cancel_repair(ticket_id: str) -> dict:
    """예약을 취소합니다. 티켓 번호로 예약을 찾아 취소하고 해당 시간대를 복구합니다."""
    result = cancel_repair_record(ticket_id)
    if "error" not in result:
        email = result.get("email", "")
        if email:
            notification = _send_notification(email, ticket_id, "cancelled")
            result["email_status"] = notification.get("status", "skipped")
        result["message"] = f"티켓 {ticket_id} 예약이 취소되었습니다."
    return result


ISSUE_TYPE_KR = {
    "sink_leak": "싱크대 누수",
    "toilet_clog": "변기 막힘",
    "boiler_issue": "보일러 고장",
    "door_lock_issue": "도어록 고장",
    "mold_issue": "곰팡이/결로",
}


def _build_email_body(notification_type: str, repair: dict) -> tuple[str, str]:
    """알림 유형에 따른 이메일 제목과 본문을 생성합니다."""
    issue_kr = ISSUE_TYPE_KR.get(repair.get("issue_type", ""), "시설 문제")
    ticket_id = repair["ticket_id"]

    if notification_type == "scheduled":
        subject = f"[KindredPM] 수리 예약 확인 - {ticket_id}"
        body = (
            f"{repair['name']}님, 안녕하세요.\n"
            f"KindredPM 유지보수 예약이 확정되었습니다.\n\n"
            f"■ 티켓 번호: {ticket_id}\n"
            f"■ 문제 유형: {issue_kr}\n"
            f"■ 방문 일시: {repair['date']} {repair['time_slot']}\n"
            f"■ 방문 주소: {repair['address']}\n\n"
            f"방문 전 현장 접근이 가능하도록 준비 부탁드립니다.\n"
            f"변경/취소가 필요하시면 KindredPM 고객센터(02-1234-5678)로 연락해주세요.\n\n"
            f"감사합니다.\nKindredPM 유지보수팀"
        )
    else:
        subject = f"[KindredPM] 예약 취소 확인 - {ticket_id}"
        body = (
            f"{repair['name']}님, 안녕하세요.\n"
            f"KindredPM 유지보수 예약이 취소되었습니다.\n\n"
            f"■ 티켓 번호: {ticket_id}\n"
            f"■ 문제 유형: {issue_kr}\n"
            f"■ 취소된 일시: {repair['date']} {repair['time_slot']}\n\n"
            f"재예약이 필요하시면 언제든 문의해주세요.\n\n"
            f"감사합니다.\nKindredPM 유지보수팀"
        )
    return subject, body


def _send_notification(email: str, ticket_id: str, notification_type: str) -> dict:
    """예약 확인/취소 이메일을 발송합니다. SMTP 미설정 시 시뮬레이션으로 폴백합니다."""
    repair = get_repair(ticket_id)
    if not repair:
        return {"status": "skipped"}

    subject, body = _build_email_body(notification_type, repair)

    smtp_user = os.environ.get("GMAIL_USER", "")
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD", "")

    if smtp_user and smtp_pass:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = email

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, email, msg.as_string())

            return {"status": "sent", "sent_to": email}
        except Exception:
            pass

    return {"status": "simulated", "sent_to": email}
