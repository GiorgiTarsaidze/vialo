"""Tests for protobuf duration parsing (fractional seconds, edge cases)."""

from __future__ import annotations

from vialo.domain.route_matrix import parse_protobuf_duration


class TestParseProtobufDuration:
    """Protobuf duration string parsing."""

    def test_integer_seconds_string(self) -> None:
        assert parse_protobuf_duration("518s") == 518

    def test_fractional_seconds_string(self) -> None:
        """Fractional seconds are rounded to nearest int."""
        assert parse_protobuf_duration("517.5s") == 518
        assert parse_protobuf_duration("517.4s") == 517
        assert parse_protobuf_duration("0.9s") == 1

    def test_integer_value(self) -> None:
        assert parse_protobuf_duration(518) == 518

    def test_float_value(self) -> None:
        assert parse_protobuf_duration(517.6) == 518

    def test_none_returns_none(self) -> None:
        assert parse_protobuf_duration(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_protobuf_duration("") is None

    def test_bare_numeric_string(self) -> None:
        assert parse_protobuf_duration("518") == 518

    def test_bare_float_string(self) -> None:
        assert parse_protobuf_duration("517.5") == 518

    def test_negative_duration(self) -> None:
        """Negative durations are parsed correctly."""
        assert parse_protobuf_duration("-5s") == -5

    def test_invalid_string_returns_none(self) -> None:
        assert parse_protobuf_duration("invalid") is None
        assert parse_protobuf_duration("abc123") is None

    def test_zero_duration(self) -> None:
        assert parse_protobuf_duration("0s") == 0
        assert parse_protobuf_duration(0) == 0

    def test_whitespace_handling(self) -> None:
        assert parse_protobuf_duration("  518s  ") == 518
        assert parse_protobuf_duration("  518  ") == 518
