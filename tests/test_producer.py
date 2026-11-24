
import json
import uuid
from datetime import datetime
from unittest.mock import patch

with patch("confluent_kafka.Producer"):
    from producer import generate_transaction


def test_transaction_required_fields():
    transaction = generate_transaction()

    expected_fields = {
        "transaction_id",
        "customer_id",
        "amount",
        "currency",
        "transaction_type",
        "merchant_category",
        "location",
        "device_id",
        "timestamp",
        "is_international",
        "is_fraud"
    }

    assert set(transaction.keys()) == expected_fields


def test_unique_transaction_ids():
    transactions = [
        generate_transaction() for _ in range(1000)
    ]

    transaction_ids = [
        transaction["transaction_id"]
        for transaction in transactions
    ]

    assert len(set(transaction_ids)) == 1000


def test_valid_transaction_id():
    transaction = generate_transaction()

    transaction_id = uuid.UUID(
        transaction["transaction_id"]
    )

    assert transaction_id.version == 4


def test_valid_customer_id():
    transaction = generate_transaction()

    customer_id = transaction["customer_id"]

    assert customer_id.startswith("CUST")
    assert customer_id[4:].isdigit()
    assert 1000 <= int(customer_id[4:]) <= 9999


def test_valid_transaction_amount():
    for _ in range(1000):
        transaction = generate_transaction()

        assert 5 <= transaction["amount"] <= 25000


def test_valid_currency():
    transaction = generate_transaction()

    assert transaction["currency"] == "USD"


def test_valid_transaction_type():
    transaction = generate_transaction()

    assert transaction["transaction_type"] in [
        "DEBIT", "CREDIT", "TRANSFER"
    ]


def test_valid_merchant_category():
    transaction = generate_transaction()

    assert transaction["merchant_category"] in [
        "Retail", "Travel", "Grocery",
        "Electronics", "Restaurant", "Online"
    ]


def test_valid_location():
    transaction = generate_transaction()

    assert transaction["location"] in [
        "New York", "Charlotte", "Dallas",
        "Chicago", "Miami", "Seattle"
    ]


def test_valid_timestamp():
    transaction = generate_transaction()

    timestamp = datetime.fromisoformat(
        transaction["timestamp"]
    )

    assert timestamp.tzinfo is not None


def test_valid_fraud_label():
    for _ in range(1000):
        transaction = generate_transaction()

        assert transaction["is_fraud"] in [0, 1]


def test_fraud_amount_consistency():
    for _ in range(1000):
        transaction = generate_transaction()

        if transaction["is_fraud"] == 1:
            assert 5000 <= transaction["amount"] <= 25000
        else:
            assert 5 <= transaction["amount"] <= 2000


def test_international_flag():
    transaction = generate_transaction()

    assert isinstance(
        transaction["is_international"], bool
    )


def test_json_serialization():
    transaction = generate_transaction()

    serialized = json.dumps(transaction)
    deserialized = json.loads(serialized)

    assert transaction == deserialized
