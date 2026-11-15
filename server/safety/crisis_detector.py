"""위기 신호 감지 모듈 (기능 3).

사용자 메시지에서 위험 표현을 찾아, 일반 AI 응답 대신
도움 기관 안내 화면을 먼저 보여 줄지 결정한다.
"""
from dataclasses import dataclass, field
from typing import List, Optional

# 비교는 공백을 제거한 문자열로 하므로 키워드에도 공백을 넣지 않는다.
CRISIS_KEYWORDS: List[str] = [
    "죽고싶",
    "자살",
    "자해",
    "사라지고싶",
    "살기싫",
]

HELP_LINES = {
    "자살예방상담전화": "109",
    "정신건강위기상담": "1577-0199",
}


@dataclass
class CrisisResult:
    is_crisis: bool
    matched: List[str] = field(default_factory=list)
    help_lines: dict = field(default_factory=dict)


def _normalize(message: str) -> str:
    """공백을 모두 제거해 '죽고 싶어' / '죽고싶어'를 같은 표현으로 본다."""
    return "".join(message.split())


def detect_crisis(message: Optional[str]) -> CrisisResult:
    """메시지에 위기 키워드가 있으면 is_crisis=True와 도움 기관 정보를 돌려준다."""
    if not message:
        return CrisisResult(is_crisis=False)

    text = _normalize(message)
    matched = [k for k in CRISIS_KEYWORDS if k in text]
    if not matched:
        return CrisisResult(is_crisis=False)
    return CrisisResult(is_crisis=True, matched=matched, help_lines=dict(HELP_LINES))
