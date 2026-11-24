
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5433"),
        database=os.getenv("DB_NAME", "fraud_detection"),
        user=os.getenv("DB_USER", "fraud_user"),
        password=os.environ["DB_PASSWORD"],
        connect_timeout=10
    )


def test_connection():

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT current_database(), current_user;")

            result = cursor.fetchone()

            print("PostgreSQL connection successful!")
            print("Database:", result[0])
            print("User:", result[1])

    finally:
        connection.close()


if __name__ == "__main__":
    test_connection()
