import os
import sys
import joblib
import pandas as pd
import psycopg2

from psycopg2.extras import execute_values

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    BooleanType,
    IntegerType
)

os.environ["PYSPARK_PYTHON"] = sys.executable

# Kafka configuration
KAFKA_SERVER = "fraud-kafka:29092"
KAFKA_TOPIC = "banking-transactions"

# PostgreSQL configuration
DB_HOST = "fraud-postgres"
DB_PORT = 5432
DB_NAME = "fraud_detection"
DB_USER = "fraud_user"

# Machine learning model path
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models",
    "fraud_model.pkl"
)

FEATURES = [
    "amount",
    "transaction_type",
    "merchant_category",
    "location",
    "is_international"
]

# Transaction schema
transaction_schema = StructType([
    StructField("transaction_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("amount", DoubleType()),
    StructField("currency", StringType()),
    StructField("transaction_type", StringType()),
    StructField("merchant_category", StringType()),
    StructField("location", StringType()),
    StructField("device_id", StringType()),
    StructField("timestamp", StringType()),
    StructField("is_international", BooleanType()),
    StructField("is_fraud", IntegerType())
])


# PostgreSQL connection
def get_db_connection():

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=os.environ["DB_PASSWORD"],
        connect_timeout=10
    )


# Test PostgreSQL connection
def test_db_connection():

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()

        print("PostgreSQL connection successful!")

    finally:
        connection.close()


# Save transactions to PostgreSQL
def save_to_postgres(pdf):

    if pdf.empty:
        return

    insert_query = """
        INSERT INTO fraud_transactions (
            transaction_id,
            customer_id,
            amount,
            currency,
            transaction_type,
            merchant_category,
            location,
            device_id,
            transaction_timestamp,
            is_international,
            is_fraud,
            predicted_fraud,
            fraud_probability,
            risk_level
        )
        VALUES %s
        ON CONFLICT (transaction_id) DO NOTHING
        RETURNING transaction_id
    """

    records = []

    for _, row in pdf.iterrows():

        records.append((
            str(row["transaction_id"]),
            str(row["customer_id"]),
            float(row["amount"]),
            str(row["currency"]),
            str(row["transaction_type"]),
            str(row["merchant_category"]),
            str(row["location"]),
            None if pd.isna(row["device_id"])
            else str(row["device_id"]),
            pd.Timestamp(row["timestamp"])
            .tz_localize("UTC")
            .to_pydatetime()
            if pd.Timestamp(row["timestamp"]).tzinfo is None
            else pd.Timestamp(row["timestamp"])
            .tz_convert("UTC")
            .to_pydatetime(),
            bool(row["is_international"]),
            int(row["is_fraud"]),
            int(row["predicted_fraud"]),
            float(row["fraud_probability"]),
            str(row["risk_level"])
        ))

    connection = get_db_connection()

    try:

        with connection.cursor() as cursor:

            inserted = execute_values(
                cursor,
                insert_query,
                records,
                page_size=1000,
                fetch=True
            )

        connection.commit()

        print("\n=== DATABASE STORAGE ===")
        print(f"Records received: {len(records)}")
        print(f"Records inserted: {len(inserted)}")
        print(
            f"Duplicates skipped: "
            f"{len(records) - len(inserted)}"
        )
        print("PostgreSQL batch committed successfully!")

    except Exception as error:

        connection.rollback()

        print(f"Database insertion failed: {error}")

        raise

    finally:

        connection.close()


def main():

    print("=" * 75)
    print("REAL-TIME AI FRAUD DETECTION SYSTEM")
    print("=" * 75)

    # Step 1: Test PostgreSQL connection
    test_db_connection()

    # Step 2: Load trained machine learning model
    model = joblib.load(MODEL_PATH)

    print("Fraud detection model loaded successfully!")

    fraud_index = list(model.classes_).index(1)

    # Step 3: Initialize Spark
    spark = (
        SparkSession.builder
        .appName("BankingFraudDetection")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.adaptive.enabled", "false")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print("Spark session initialized successfully!")

    # Step 4: Read transactions from Kafka
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_SERVER)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("maxOffsetsPerTrigger", "1000")
        .load()
    )

    # Step 5: Convert Kafka messages into JSON
    raw_df = kafka_df.select(
        col("value").cast("string").alias("raw_json"),
        col("partition"),
        col("offset")
    )

    parsed_df = raw_df.select(
        from_json(
            col("raw_json"),
            transaction_schema
        ).alias("data"),
        col("partition"),
        col("offset")
    )

    transactions_df = parsed_df.select(
        "data.*",
        "partition",
        "offset"
    )

    # Step 6: Convert transaction timestamp
    transactions_df = transactions_df.withColumn(
        "timestamp",
        to_timestamp(col("timestamp"))
    )

    # Step 7: Validate transactions
    valid_df = transactions_df.filter(
        col("transaction_id").isNotNull()
        & col("customer_id").isNotNull()
        & col("amount").isNotNull()
        & (col("amount") > 0)
        & col("timestamp").isNotNull()
        & (col("currency") == "USD")
        & col("transaction_type").isNotNull()
        & col("merchant_category").isNotNull()
        & col("location").isNotNull()
        & col("is_international").isNotNull()
        & col("is_fraud").isin(0, 1)
    )

    # Step 8: Process each streaming micro-batch
    def process_batch(batch_df, batch_id):

        pdf = batch_df.toPandas()

        if pdf.empty:
            return

        features = pdf[FEATURES]

        # Generate fraud predictions
        pdf["predicted_fraud"] = model.predict(features)

        # Generate fraud probabilities
        pdf["fraud_probability"] = model.predict_proba(
            features
        )[:, fraud_index]

        # Assign risk levels
        pdf["risk_level"] = pdf["fraud_probability"].apply(
            lambda probability:
            "HIGH" if probability >= 0.80
            else "MEDIUM" if probability >= 0.40
            else "LOW"
        )

        # Calculate batch statistics
        total = len(pdf)

        fraud_count = int(
            pdf["predicted_fraud"].sum()
        )

        legitimate_count = total - fraud_count

        total_amount = pdf["amount"].sum()

        fraud_amount = pdf.loc[
            pdf["predicted_fraud"] == 1,
            "amount"
        ].sum()

        print("\n" + "=" * 75)
        print(f"BATCH ID: {batch_id}")
        print(f"Transactions processed: {total}")
        print(f"Legitimate transactions: {legitimate_count}")
        print(f"Suspected fraud transactions: {fraud_count}")
        print(f"Total transaction amount: ${total_amount:,.2f}")
        print(f"Suspected fraud amount: ${fraud_amount:,.2f}")
        print("=" * 75)

        # Step 9: Store predictions in PostgreSQL
        save_to_postgres(pdf)

        # Step 10: Display processed transactions
        display_columns = [
            "customer_id",
            "amount",
            "is_fraud",
            "predicted_fraud",
            "fraud_probability",
            "risk_level"
        ]

        print(
            pdf[display_columns]
            .round(4)
            .to_string(index=False)
        )

        # Step 11: Generate real-time fraud alerts
        fraud_alerts = pdf[
            pdf["predicted_fraud"] == 1
        ]

        for _, transaction in fraud_alerts.iterrows():

            print("\n" + "!" * 60)
            print("FRAUD ALERT")
            print("!" * 60)

            print(
                f"Transaction ID: "
                f"{transaction['transaction_id']}"
            )

            print(
                f"Customer: "
                f"{transaction['customer_id']}"
            )

            print(
                f"Amount: "
                f"${transaction['amount']:,.2f}"
            )

            print(
                f"Transaction type: "
                f"{transaction['transaction_type']}"
            )

            print(
                f"Merchant: "
                f"{transaction['merchant_category']}"
            )

            print(
                f"Location: "
                f"{transaction['location']}"
            )

            print(
                f"International: "
                f"{transaction['is_international']}"
            )

            print(
                f"Fraud probability: "
                f"{transaction['fraud_probability']:.2%}"
            )

            print(
                f"Risk level: "
                f"{transaction['risk_level']}"
            )

            print("!" * 60)

    # Step 12: Start real-time streaming
    query = (
        valid_df.writeStream
        .foreachBatch(process_batch)
        .outputMode("append")
        .trigger(processingTime="5 seconds")
        .start()
    )

    print("\nListening for banking transactions...")
    print("Real-time fraud detection is active.")
    print("PostgreSQL storage is enabled.")

    try:

        query.awaitTermination()

    except KeyboardInterrupt:

        print("\nStopping stream processor...")

    finally:

        query.stop()
        spark.stop()

        print("Stream processor stopped.")


if __name__ == "__main__":
    main()