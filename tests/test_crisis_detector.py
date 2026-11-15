import pytest

from server.safety import detect_crisis


def test_detects_crisis_keyword():
    assert detect_crisis("요즘 너무 힘들어서 죽고 싶어").is_crisis


@pytest.mark.parametrize("message", ["죽고싶어", "죽고  싶다", "그냥 사라지고 싶어"])
def test_detects_regardless_of_spacing(message):
    assert detect_crisis(message).is_crisis


def test_normal_message_is_not_crisis():
    result = detect_crisis("오늘 시험 끝나서 기분 좋아!")
    assert not result.is_crisis
    assert result.help_lines == {}


@pytest.mark.parametrize("message", ["", None])
def test_empty_message_is_safe(message):
    assert not detect_crisis(message).is_crisis


def test_crisis_result_includes_help_lines():
    result = detect_crisis("자해하고 싶은 생각이 들어")
    assert result.help_lines["자살예방상담전화"] == "109"
