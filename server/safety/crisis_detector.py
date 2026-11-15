"""위기 신호 감지 모듈 (기능 3).

사용자 메시지에서 위험 표현을 찾아, 일반 AI 응답 대신
도움 기관 안내 화면을 먼저 보여 줄지 결정한다.
"""
from dataclasses import dataclass, field

CRISIS_KEYWORDS = [
    "죽고 싶",
    "자살",
    "자해",
    "사라지고 싶",
    "살기 싫",
]

HELP_LINES = {
    "자살예방상담전화": "109",
    "정신건강위기상담": "1577-0199",
}


@dataclass
class CrisisResult:
    is_crisis: bool
    matched: list = field(default_factory=list)


def detect_crisis(message):
    matched = [k for k in CRISIS_KEYWORDS if k in message]
    return CrisisResult(is_crisis=len(matched) > 0, matched=matched)
