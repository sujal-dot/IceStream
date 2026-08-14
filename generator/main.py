"""Main CLI entrypoint for the IceStream High-Throughput E-Commerce Event Generator."""

import logging
import signal
import sys
import time
from typing import Optional

from generator.config import GeneratorConfig, parse_args
from generator.event_generator import EventGeneratorEngine
from generator.producer import EventProducer
from generator.utils import RateLimiter, StatsTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("generator.main")

# Global graceful shutdown flag
_RUNNING = True


def _signal_handler(signum, frame):
    global _RUNNING
    print("\n[Shutdown] Signal received. Flushing Kafka producer and shutting down...")
    _RUNNING = False


def run_generator(config: GeneratorConfig):
    """Run the event generator loop until duration expires or shutdown signal received."""
    global _RUNNING
    _RUNNING = True

    # Register SIGINT / SIGTERM handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    stats_tracker = StatsTracker()
    print(
        stats_tracker.format_stats_header(
            {
                "bootstrap_server": config.bootstrap_server,
                "topic": config.topic,
                "rate": config.rate,
                "error_rate": config.error_rate,
                "error_types": config.error_types,
                "seed": config.seed,
            }
        )
    )

    try:
        producer = EventProducer(bootstrap_servers=config.bootstrap_server)
    except Exception as e:
        logger.error(f"Failed to connect to Kafka at {config.bootstrap_server}: {e}")
        sys.exit(1)

    engine = EventGeneratorEngine(config=config, producer=producer)
    # Dynamically choose batch size for rate limiter (e.g. 50 events per batch or 5% of rate)
    batch_size = max(10, min(100, int(config.rate * 0.05)))
    rate_limiter = RateLimiter(target_rate=config.rate, batch_size=batch_size)

    last_log_time = time.perf_counter()

    try:
        while _RUNNING:
            engine.produce_next_event()
            rate_limiter.sleep_if_needed()

            now = time.perf_counter()
            # Log throughput stats periodically
            if now - last_log_time >= config.log_interval:
                stats = stats_tracker.get_stats(
                    generated=producer.generated_count,
                    published=producer.published_count,
                    failed=producer.failed_count,
                    valid=producer.valid_count,
                    injected_errors=producer.injected_error_count,
                )
                print(stats_tracker.format_stats_log(stats))
                last_log_time = now

            # Check if duration limit reached
            if config.duration and (now - stats_tracker.start_time) >= config.duration:
                print(
                    f"\n[Duration Limit] Configured duration of {config.duration}s reached."
                )
                break

    except Exception as e:
        logger.error(f"Unexpected error in generator loop: {e}", exc_info=True)
    finally:
        # Graceful shutdown: flush & close Kafka producer
        print("\nFlushing pending Kafka messages...")
        producer.flush(timeout=5.0)

        # Print final statistics summary
        final_stats = stats_tracker.get_stats(
            generated=producer.generated_count,
            published=producer.published_count,
            failed=producer.failed_count,
            valid=producer.valid_count,
            injected_errors=producer.injected_error_count,
        )

        print("\n" + "=" * 50)
        print("Final Statistics Summary")
        print("=" * 50)
        print(f"Elapsed Time       : {final_stats['elapsed_sec']:.2f}s")
        print(f"Total Generated    : {final_stats['generated']}")
        print(f"Total Published    : {final_stats['published']}")
        print(f"Publish Failures   : {final_stats['failed']}")
        print(f"Valid Events       : {final_stats['valid']}")
        print(
            f"Injected Errors    : {final_stats['injected_errors']} ({final_stats['observed_error_pct']:.2f}%)"
        )
        print(f"Average Throughput : {final_stats['average_rate']:.1f} events/sec")
        print("=" * 50)

        producer.close()
        print("Generator stopped cleanly.\n")


def main():
    config = parse_args()
    run_generator(config)


if __name__ == "__main__":
    main()
