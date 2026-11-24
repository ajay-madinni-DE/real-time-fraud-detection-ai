
from database import get_connection


def test_database_connection():
    connection = get_connection()

    try:
        assert connection.closed == 0
    finally:
        connection.close()


def test_database_name():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            result = cursor.fetchone()

            assert result[0] == "fraud_detection"
    finally:
        connection.close()


def test_transactions_table_exists():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'fraud_transactions'
                );
            """)

            assert cursor.fetchone()[0] is True
    finally:
        connection.close()


def test_transactions_available():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM fraud_transactions;"
            )

            assert cursor.fetchone()[0] > 0
    finally:
        connection.close()
