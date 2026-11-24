
from database import get_connection


def fetch_count(query):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchone()[0]
    finally:
        connection.close()


def test_no_duplicate_transactions():
    result = fetch_count("""
        SELECT COUNT(*) - COUNT(DISTINCT transaction_id)
        FROM fraud_transactions;
    """)

    assert result == 0


def test_valid_transaction_amounts():
    result = fetch_count("""
        SELECT COUNT(*)
        FROM fraud_transactions
        WHERE amount IS NULL OR amount <= 0;
    """)

    assert result == 0


def test_no_missing_ids():
    result = fetch_count("""
        SELECT COUNT(*)
        FROM fraud_transactions
        WHERE transaction_id IS NULL
        OR customer_id IS NULL;
    """)

    assert result == 0


def test_valid_fraud_probability():
    result = fetch_count("""
        SELECT COUNT(*)
        FROM fraud_transactions
        WHERE fraud_probability IS NULL
        OR fraud_probability < 0
        OR fraud_probability > 1;
    """)

    assert result == 0


def test_valid_risk_levels():
    result = fetch_count("""
        SELECT COUNT(*)
        FROM fraud_transactions
        WHERE risk_level IS NULL
        OR risk_level NOT IN ('HIGH', 'MEDIUM', 'LOW');
    """)

    assert result == 0


def test_valid_fraud_predictions():
    result = fetch_count("""
        SELECT COUNT(*)
        FROM fraud_transactions
        WHERE predicted_fraud IS NULL
        OR predicted_fraud NOT IN (0, 1);
    """)

    assert result == 0
