from .db import (
    book_slot,
    create_repair,
    generate_ticket_id,
    get_available_slots,
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
        return {"instructions": QUICK_FIX_DATA[issue_type]}
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
    email: str = "",
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
        email=email or None,
    )
    repair["message"] = (
        f"{name}님, {date} {time_slot}에 수리 기사가 방문할 예정입니다. 티켓 번호: {ticket_id}"
    )
    return repair
