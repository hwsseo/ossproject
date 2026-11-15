from server.safety import detect_crisis


def test_detects_crisis_keyword():
    assert detect_crisis("요즘 너무 힘들어서 죽고 싶어").is_crisis


def test_normal_message_is_not_crisis():
    assert not detect_crisis("오늘 시험 끝나서 기분 좋아!").is_crisis
