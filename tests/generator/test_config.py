"""Unit tests for configuration parsing and validation."""

import pytest
from generator.config import GeneratorConfig, parse_args, ALL_ERROR_TYPES


def test_default_config():
    config = GeneratorConfig()
    assert config.rate == 1000
    assert config.error_rate == 0.0
    assert config.error_probability == 0.0
    assert config.bootstrap_server == "localhost:9092"
    assert config.topic == "checkout-events"
    assert config.error_types == ALL_ERROR_TYPES


def test_custom_config_parsing():
    args = [
        "--rate", "2500",
        "--error-rate", "0.5",
        "--bootstrap-server", "127.0.0.1:9092",
        "--topic", "test-topic",
        "--error-types", "null_amount,negative_amount",
        "--seed", "123",
        "--duration", "15",
    ]
    config = parse_args(args)
    assert config.rate == 2500
    assert config.error_rate == 0.5
    assert config.error_probability == 0.005
    assert config.bootstrap_server == "127.0.0.1:9092"
    assert config.topic == "test-topic"
    assert config.error_types == ["null_amount", "negative_amount"]
    assert config.seed == 123
    assert config.duration == 15.0


def test_error_rate_interpretation():
    # Verify 0.5 error rate means 0.5% (0.005 probability)
    config = GeneratorConfig(error_rate=0.5)
    assert config.error_probability == 0.005

    # Verify 5.0 error rate means 5% (0.05 probability)
    config5 = GeneratorConfig(error_rate=5.0)
    assert config5.error_probability == 0.05


def test_invalid_config_values():
    with pytest.raises(ValueError, match="Target rate must be a positive integer"):
        GeneratorConfig(rate=0)

    with pytest.raises(ValueError, match="Error rate must be between 0.0 and 100.0"):
        GeneratorConfig(error_rate=-1.0)

    with pytest.raises(ValueError, match="Error rate must be between 0.0 and 100.0"):
        GeneratorConfig(error_rate=105.0)

    with pytest.raises(ValueError, match="Unsupported error types"):
        GeneratorConfig(error_types=["invalid_type_name"])
