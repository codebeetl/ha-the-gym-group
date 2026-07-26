"""Tests for URL-building helpers in const.py."""

from custom_components.the_gym_group.const import (
    build_busyness_url,
    build_checkin_history_url,
    build_login_url,
    build_schedule_url,
    is_safe_header_value,
    is_valid_host,
)


def test_build_login_url() -> None:
    """The login URL is built from host + the fixed login path."""
    assert build_login_url("thegymgroup.netpulse.com") == (
        "https://thegymgroup.netpulse.com/np/exerciser/login"
    )


def test_build_busyness_url() -> None:
    """The busyness URL interpolates the user id into its path template."""
    assert build_busyness_url("abc-123", "thegymgroup.netpulse.com") == (
        "https://thegymgroup.netpulse.com"
        "/np/thegymgroup/v1.0/exerciser/abc-123/gym-busyness"
    )


def test_build_checkin_history_url() -> None:
    """Date range query params are appended in the expected order."""
    result = build_checkin_history_url(
        "abc-123",
        "2025-04-01T09:00:00",
        "2025-04-03T09:00:00",
        "thegymgroup.netpulse.com",
    )
    assert result == (
        "https://thegymgroup.netpulse.com/np/exercisers/abc-123/check-ins/history"
        "?startDate=2025-04-01T09:00:00&endDate=2025-04-03T09:00:00"
    )


def test_build_schedule_url() -> None:
    """Epoch-millisecond query params are appended in the expected order."""
    result = build_schedule_url(
        "abc-123", 1_750_000_000_000, 1_750_600_000_000, "thegymgroup.netpulse.com"
    )
    assert result == (
        "https://thegymgroup.netpulse.com/np/exerciser/abc-123/schedule"
        "?startDateTime=1750000000000&endDateTime=1750600000000"
    )


def test_is_valid_host_accepts_netpulse_subdomains() -> None:
    """A bare hostname under netpulse.com is allowed."""
    assert is_valid_host("thegymgroup.netpulse.com") is True
    assert is_valid_host("netpulse.com") is True


def test_is_valid_host_rejects_other_domains() -> None:
    """A hostname outside netpulse.com is rejected."""
    assert is_valid_host("attacker.example.com") is False
    assert is_valid_host("") is False


def test_is_safe_header_value_accepts_normal_text() -> None:
    """A normal header override value is accepted."""
    assert is_safe_header_value("okhttp/4.12.0") is True


def test_is_safe_header_value_rejects_control_characters() -> None:
    """CRLF or other control characters must be rejected."""
    assert is_safe_header_value("evil\r\nX-Injected: true") is False
    assert is_safe_header_value("evil\x00null") is False
