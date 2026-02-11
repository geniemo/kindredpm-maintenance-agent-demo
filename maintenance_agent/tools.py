QUICK_FIX_DATA = {
    "sink_leak": (
        "1. 싱크대 아래쪽에 있는 지수밸브(수도 잠금 장치)를 시계 방향으로 돌려서 잠가주세요.\n"
        "2. 누수 부위 아래에 양동이나 대야를 받쳐 물을 받아주세요.\n"
        "3. 배관 주변을 수건으로 감싸 물이 튀는 것을 방지해주세요.\n"
        "4. 주변에 전기 콘센트가 있다면 물이 닿지 않도록 주의해주세요."
    ),
}


def provide_quick_fix(issue_type: str) -> dict:
    """응급조치 방법을 안내합니다. issue_type에 해당하는 응급조치 절차를 반환합니다."""
    if issue_type in QUICK_FIX_DATA:
        return {"instructions": QUICK_FIX_DATA[issue_type]}
    return {"error": f"지원하지 않는 문제 유형입니다: {issue_type}"}
