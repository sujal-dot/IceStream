"""Realistic synthetic data generator for e-commerce checkout events."""

import datetime
import random
import uuid
from typing import Any, Dict, List, Optional
from faker import Faker

from generator.event_schema import CheckoutEvent

# Pre-defined product catalog with IDs and realistic unit prices (INR)
PRODUCT_CATALOG = [
    {"id": "PROD001", "name": "Laptop", "price": 54990.00},
    {"id": "PROD002", "name": "Smartphone", "price": 24990.00},
    {"id": "PROD003", "name": "Headphones", "price": 2990.00},
    {"id": "PROD004", "name": "Monitor", "price": 14990.00},
    {"id": "PROD005", "name": "Keyboard", "price": 1990.00},
    {"id": "PROD006", "name": "Mouse", "price": 990.00},
    {"id": "PROD007", "name": "Smartwatch", "price": 4990.00},
    {"id": "PROD008", "name": "Tablet", "price": 19990.00},
    {"id": "PROD009", "name": "Power Bank", "price": 1490.00},
    {"id": "PROD010", "name": "Camera", "price": 44990.00},
]

# Weighted distributions
PAYMENT_METHODS = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING", "WALLET", "COD"]
PAYMENT_METHOD_WEIGHTS = [0.50, 0.20, 0.15, 0.08, 0.05, 0.02]

PAYMENT_STATUSES = ["SUCCESS", "FAILED", "PENDING"]
PAYMENT_STATUS_WEIGHTS = [0.85, 0.10, 0.05]

DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.60, 0.30, 0.10]

QUANTITIES = [1, 2, 3, 4, 5]
QUANTITY_WEIGHTS = [0.65, 0.20, 0.08, 0.05, 0.02]


class DataGenerator:
    """Generates realistic synthetic checkout event payloads."""

    def __init__(self, seed: Optional[int] = None, customer_pool_size: int = 5000):
        self._seed = seed
        self._rnd = random.Random(seed)
        self.fake = Faker()
        if seed is not None:
            Faker.seed(seed)

        # Pre-generate customer pool for consistency
        self.customers: List[str] = [
            f"CUS{i:06d}" for i in range(1, customer_pool_size + 1)
        ]

    def set_seed(self, seed: int):
        """Re-seed the generator."""
        self._seed = seed
        self._rnd = random.Random(seed)
        Faker.seed(seed)

    def generate_utc_timestamp_str(
        self, dt: Optional[datetime.datetime] = None
    ) -> str:
        """Generate timezone-aware UTC ISO 8601 string formatted with milliseconds."""
        if dt is None:
            dt = datetime.datetime.now(datetime.timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)

        # Format ISO with Z suffix: YYYY-MM-DDTHH:MM:SS.sssZ
        millis = dt.microsecond // 1000
        return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{millis:03d}Z"

    def generate_valid_event(self) -> Dict[str, Any]:
        """Generate a realistic, valid checkout event dictionary."""
        now = datetime.datetime.now(datetime.timezone.utc)
        event_time_str = self.generate_utc_timestamp_str(now)

        customer_id = self._rnd.choice(self.customers)
        product = self._rnd.choice(PRODUCT_CATALOG)
        quantity = self._rnd.choices(QUANTITIES, weights=QUANTITY_WEIGHTS)[0]
        unit_price = product["price"]
        amount = round(quantity * unit_price, 2)

        payment_method = self._rnd.choices(
            PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS
        )[0]
        payment_status = self._rnd.choices(
            PAYMENT_STATUSES, weights=PAYMENT_STATUS_WEIGHTS
        )[0]
        device = self._rnd.choices(DEVICES, weights=DEVICE_WEIGHTS)[0]

        event_id = f"evt_{uuid.UUID(int=self._rnd.getrandbits(128)).hex[:16]}"
        session_id = f"SES{self._rnd.randint(100000, 999999)}"
        order_id = f"ORD{self._rnd.randint(1000000, 9999999)}"

        event = CheckoutEvent(
            event_id=event_id,
            event_time=event_time_str,
            event_type="checkout",
            customer_id=customer_id,
            session_id=session_id,
            order_id=order_id,
            product_id=product["id"],
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
            currency="INR",
            payment_method=payment_method,
            payment_status=payment_status,
            device=device,
            country="IN",
            source="web",
            source_version="v1",
        )

        return event.to_dict()
