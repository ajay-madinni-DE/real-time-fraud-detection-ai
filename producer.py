import json
import random
import time
import uuid
from datetime import datetime, timezone
from confluent_kafka import Producer

producer = Producer({
    "bootstrap.servers": "127.0.0.1:9092",
    "broker.address.family": "v4",
    "client.id": "banking-producer",
    "enable.idempotence": True
})

TOPIC = "banking-transactions"

LOCATIONS = ["New York", "Charlotte", "Dallas",
             "Chicago", "Miami", "Seattle"]

MERCHANTS = ["Retail", "Travel", "Grocery",
             "Electronics", "Restaurant", "Online"]


def generate_transaction():

    suspicious = random.random() < 0.05

    if suspicious:
        amount = round(random.uniform(5000, 25000), 2)
    else:
        amount = round(random.uniform(5, 2000), 2)

    return {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": f"CUST{random.randint(1000, 9999)}",
        "amount": amount,
        "currency": "USD",
        "transaction_type": random.choice(
            ["DEBIT", "CREDIT", "TRANSFER"]
        ),
        "merchant_category": random.choice(MERCHANTS),
        "location": random.choice(LOCATIONS),
        "device_id": f"DEV{random.randint(100, 999)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_international": random.random() < (
            0.8 if suspicious else 0.05
        ),
        "is_fraud": int(suspicious)
    }


def delivery_report(error, message):

    if error:
        print(f"Delivery failed: {error}")
    else:
        print(
            f"Delivered to partition {message.partition()} "
            f"| Offset: {message.offset()}"
        )


def main():

    print("=== REAL-TIME BANKING PRODUCER ===")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:

            transaction = generate_transaction()

            producer.produce(
                TOPIC,
                key=transaction["customer_id"],
                value=json.dumps(transaction),
                callback=delivery_report
            )

            producer.poll(0)

            print(
                f"Customer: {transaction['customer_id']} | "
                f"Amount: ${transaction['amount']:,.2f} | "
                f"Fraud label: {transaction['is_fraud']}"
            )

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopping producer...")

    finally:
        remaining = producer.flush(10)
        print(f"Undelivered messages: {remaining}")
        print("Producer stopped.")


if __name__ == "__main__":
    main()