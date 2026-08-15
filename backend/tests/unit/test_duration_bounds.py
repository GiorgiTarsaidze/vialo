"""Tests for duration bounds validation with committed spec values."""

from __future__ import annotations

from vialo.domain.duration_bounds import (
    CATEGORY_BOUNDS,
    default_duration,
    parse_duration_text,
    validate_model_duration,
    validate_user_duration,
)
from vialo.models.providers import StopCategory


class TestValidateModelDuration:
    def test_within_bounds(self) -> None:
        assert validate_model_duration(StopCategory.LANDMARK, 45) is True

    def test_at_min_bound(self) -> None:
        # Landmark min is 30 per spec
        assert validate_model_duration(StopCategory.LANDMARK, 30) is True

    def test_at_max_bound(self) -> None:
        # Landmark max is 75 per spec
        assert validate_model_duration(StopCategory.LANDMARK, 75) is True

    def test_below_min(self) -> None:
        assert validate_model_duration(StopCategory.LANDMARK, 29) is False

    def test_above_max(self) -> None:
        assert validate_model_duration(StopCategory.LANDMARK, 76) is False

    def test_museum_bounds(self) -> None:
        # Museum: 60/90/180
        assert validate_model_duration(StopCategory.MUSEUM_GALLERY, 60) is True
        assert validate_model_duration(StopCategory.MUSEUM_GALLERY, 180) is True
        assert validate_model_duration(StopCategory.MUSEUM_GALLERY, 59) is False
        assert validate_model_duration(StopCategory.MUSEUM_GALLERY, 181) is False

    def test_quick_viewpoint_bounds(self) -> None:
        # Quick: 15/20/30
        assert validate_model_duration(StopCategory.QUICK_VIEWPOINT, 15) is True
        assert validate_model_duration(StopCategory.QUICK_VIEWPOINT, 30) is True
        assert validate_model_duration(StopCategory.QUICK_VIEWPOINT, 31) is False

    def test_experience_bounds(self) -> None:
        # Experience: 60/120/240
        assert validate_model_duration(StopCategory.EXPERIENCE_TOUR, 60) is True
        assert validate_model_duration(StopCategory.EXPERIENCE_TOUR, 240) is True
        assert validate_model_duration(StopCategory.EXPERIENCE_TOUR, 59) is False

    def test_other_bounds(self) -> None:
        # Other: 30/60/90
        assert validate_model_duration(StopCategory.OTHER, 30) is True
        assert validate_model_duration(StopCategory.OTHER, 90) is True
        assert validate_model_duration(StopCategory.OTHER, 91) is False


class TestValidateUserDuration:
    def test_minimum(self) -> None:
        assert validate_user_duration(15) is True

    def test_maximum(self) -> None:
        assert validate_user_duration(240) is True

    def test_below_minimum(self) -> None:
        assert validate_user_duration(14) is False

    def test_above_maximum(self) -> None:
        assert validate_user_duration(241) is False


class TestDefaultDuration:
    def test_known_category(self) -> None:
        assert default_duration(StopCategory.QUICK_VIEWPOINT) == 20

    def test_landmark_default(self) -> None:
        assert default_duration(StopCategory.LANDMARK) == 45

    def test_museum_default(self) -> None:
        assert default_duration(StopCategory.MUSEUM_GALLERY) == 90

    def test_all_categories_have_bounds(self) -> None:
        for cat in StopCategory:
            assert cat in CATEGORY_BOUNDS


class TestParseDurationText:
    def test_minutes_forms(self) -> None:
        assert parse_duration_text("30 minutes") == 30
        assert parse_duration_text("30 min") == 30
        assert parse_duration_text("30m") == 30
        assert parse_duration_text("45 mins") == 45

    def test_hours_forms(self) -> None:
        assert parse_duration_text("1 hour") == 60
        assert parse_duration_text("2 hours") == 120
        assert parse_duration_text("1.5 hours") == 90
        assert parse_duration_text("2h") == 120
        assert parse_duration_text("1hr") == 60
        assert parse_duration_text("half an hour") == 30
        assert parse_duration_text("1h 30m") == 90

    def test_hours_and_minutes(self) -> None:
        assert parse_duration_text("1 hour 30 minutes") == 90
        assert parse_duration_text("2 hours and 15 min") == 135

    def test_bare_number(self) -> None:
        assert parse_duration_text("60") == 60
        assert parse_duration_text("90") == 90

    def test_whitespace_handling(self) -> None:
        assert parse_duration_text("  30 minutes  ") == 30

    def test_none_returns_none(self) -> None:
        assert parse_duration_text(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_duration_text("") is None

    def test_invalid_string_returns_none(self) -> None:
        assert parse_duration_text("hello world") is None

    def test_zero_returns_none(self) -> None:
        assert parse_duration_text("0 minutes") is None
        assert parse_duration_text("0") is None
