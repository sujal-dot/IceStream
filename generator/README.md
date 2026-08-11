# Event Generator Component

## Component Purpose
The `generator/` module will serve as the event simulation engine for the IceStream platform. It simulates real-world transaction and user activity telemetry, generating continuous high-velocity JSON event streams with customizable anomaly injection capabilities.

## Planned Responsibility
- Generate synthetically realistic e-commerce/financial event streams.
- Support controllable event generation rates (events/sec).
- Inject deterministic and random failure scenarios (null values, negative amounts, schema mutations, corrupt timestamps).
- Publish event payloads directly to Apache Kafka topics.

## Expected Inputs
- Configuration parameters (events/sec, anomaly ratio, seed values, Kafka bootstrap servers).
- User commands via CLI or API to trigger specific failure injection patterns.

## Expected Outputs
- Formatted JSON event messages published to Kafka topic `raw-events`.

## Future Implementation Phase
- **Implementation Phase**: Phase 2 (Data Ingestion & Event Simulation).
- **Status**: Architecture Target / Planned. No implementation code present on Day 1.
