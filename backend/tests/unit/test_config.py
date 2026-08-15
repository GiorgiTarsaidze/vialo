"""Unit tests for configuration loading and validation."""

from __future__ import annotations

import pytest

from vialo.config import load_config


class TestConfigRejectsInvalidBudgetAndRates:
    def test_zero_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Budget of 0 is rejected."""
        monkeypatch.setenv("BEDROCK_MONTHLY_BUDGET_USD", "0")
        with pytest.raises(ValueError, match="strictly positive"):
            load_config()

    def test_negative_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative budget is rejected."""
        monkeypatch.setenv("BEDROCK_MONTHLY_BUDGET_USD", "-1.00")
        with pytest.raises(ValueError, match="strictly positive"):
            load_config()

    def test_zero_input_rate_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Input rate of 0 is rejected."""
        monkeypatch.setenv("BEDROCK_INPUT_USD_PER_MILLION_TOKENS", "0")
        with pytest.raises(ValueError, match="strictly positive"):
            load_config()

    def test_negative_input_rate_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative input rate is rejected."""
        monkeypatch.setenv("BEDROCK_INPUT_USD_PER_MILLION_TOKENS", "-2.00")
        with pytest.raises(ValueError, match="strictly positive"):
            load_config()

    def test_zero_output_rate_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Output rate of 0 is rejected."""
        monkeypatch.setenv("BEDROCK_OUTPUT_USD_PER_MILLION_TOKENS", "0")
        with pytest.raises(ValueError, match="strictly positive"):
            load_config()

    def test_negative_output_rate_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative output rate is rejected."""
        monkeypatch.setenv("BEDROCK_OUTPUT_USD_PER_MILLION_TOKENS", "-10.00")
        with pytest.raises(ValueError, match="strictly positive"):
            load_config()

    def test_valid_config_loads_successfully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid positive values load successfully."""
        from decimal import Decimal

        config = load_config()
        assert config.bedrock_monthly_budget_micro_usd == 5_000_000
        assert config.bedrock_input_usd_per_million == Decimal("4.00")
        assert config.bedrock_output_usd_per_million == Decimal("20.00")

    def test_budget_uses_exact_decimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Budget uses exact Decimal arithmetic, not floating point."""
        monkeypatch.setenv("BEDROCK_MONTHLY_BUDGET_USD", "0.01")
        config = load_config()
        # 0.01 * 1000000 = 10000 exactly with Decimal
        assert config.bedrock_monthly_budget_micro_usd == 10000

    def test_non_numeric_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-numeric budget raises ValueError."""
        monkeypatch.setenv("BEDROCK_MONTHLY_BUDGET_USD", "five")
        with pytest.raises(ValueError, match="valid decimal"):
            load_config()

    def test_missing_required_variable_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing required env var raises ValueError."""
        monkeypatch.delenv("GOOGLE_SERVER_KEY", raising=False)
        with pytest.raises(ValueError, match="Missing required"):
            load_config()

    def test_nan_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NaN budget is rejected as non-finite."""
        monkeypatch.setenv("BEDROCK_MONTHLY_BUDGET_USD", "NaN")
        with pytest.raises(ValueError, match="finite"):
            load_config()

    def test_infinity_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Infinity budget is rejected as non-finite."""
        monkeypatch.setenv("BEDROCK_MONTHLY_BUDGET_USD", "Infinity")
        with pytest.raises(ValueError, match="finite"):
            load_config()

    def test_negative_infinity_input_rate_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """-Infinity input rate is rejected as non-finite."""
        monkeypatch.setenv("BEDROCK_INPUT_USD_PER_MILLION_TOKENS", "-Infinity")
        with pytest.raises(ValueError, match="finite"):
            load_config()

    def test_nan_output_rate_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NaN output rate is rejected."""
        monkeypatch.setenv("BEDROCK_OUTPUT_USD_PER_MILLION_TOKENS", "NaN")
        with pytest.raises(ValueError, match="finite"):
            load_config()
