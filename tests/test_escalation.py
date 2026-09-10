import pytest
from datetime import datetime, timedelta, timezone

def get_escalation_level(current_level, last_attempt_time):
    now = datetime.now(timezone.utc)
    if current_level == 1 and (now - last_attempt_time) > timedelta(hours=24):
        return 2
    if current_level == 2 and (now - last_attempt_time) > timedelta(hours=48):
        return 3
    return current_level

def test_escalation_from_level_1_to_2():
    level = get_escalation_level(1, datetime.now(timezone.utc) - timedelta(hours=25))
    assert level == 2

def test_escalation_from_level_2_to_3():
    level = get_escalation_level(2, datetime.now(timezone.utc) - timedelta(hours=49))
    assert level == 3

def test_no_escalation_before_timeout():
    level = get_escalation_level(1, datetime.now(timezone.utc) - timedelta(hours=2))
    assert level == 1

def test_max_escalation_level():
    level = get_escalation_level(3, datetime.now(timezone.utc) - timedelta(hours=100))
    assert level == 3
