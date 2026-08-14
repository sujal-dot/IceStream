# IceStream Generator Test Suite

Unit and integration tests for the IceStream checkout event generator component.

## Test Files

- `test_config.py`: Unit tests for CLI parsing, configuration defaults, and error rate probability calculations.
- `test_event_generator.py`: Unit tests for baseline clean event structure, required fields, price calculations, UTC ISO timestamps, and seed reproducibility.
- `test_error_injector.py`: Unit tests for all 8 supported error injection types and probabilistic error distribution.
- `test_kafka_integration.py`: End-to-end integration test publishing events to local Kafka cluster and reading them back via a test consumer.

## Running Tests

Run unit tests (no Kafka required):

```bash
.venv/bin/pytest tests/generator/test_config.py tests/generator/test_event_generator.py tests/generator/test_error_injector.py
```

Run all tests including Kafka integration test:

```bash
.venv/bin/pytest tests/generator/
```
