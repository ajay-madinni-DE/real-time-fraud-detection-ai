import os
import re
import pandas as pd
import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5433"),
        database=os.getenv("DB_NAME", "fraud_detection"),
        user=os.getenv("DB_USER", "fraud_user"),
        password=os.environ["DB_PASSWORD"]
    )


def run_query(query, params=None):

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [
                desc[0] for desc in cursor.description
            ]
            return pd.DataFrame(
                cursor.fetchall(),
                columns=columns
            )

    finally:
        connection.close()


def fraud_summary():

    df = run_query("""
        SELECT
            COUNT(*) AS total_transactions,
            COUNT(*) FILTER (
                WHERE predicted_fraud = 1
            ) AS suspected_fraud,
            COUNT(*) FILTER (
                WHERE predicted_fraud = 0
            ) AS legitimate_transactions,
            COALESCE(SUM(amount), 0) AS total_value,
            COALESCE(SUM(amount) FILTER (
                WHERE predicted_fraud = 1
            ), 0) AS fraud_exposure
        FROM fraud_transactions
    """)

    row = df.iloc[0]

    total = int(row["total_transactions"])
    fraud = int(row["suspected_fraud"])

    rate = (fraud / total * 100) if total else 0

    return f"""
### Fraud Investigation Summary

- Total transactions: {total:,}
- Suspected fraud: {fraud:,}
- Predicted legitimate: {int(row['legitimate_transactions']):,}
- Fraud flag rate: {rate:.2f}%
- Total transaction value: ${row['total_value']:,.2f}
- Potential fraud exposure: ${row['fraud_exposure']:,.2f}

**Recommendation:** Review high-risk transactions
before taking any action.
"""


def highest_risk_transactions(limit=10):

    return run_query("""
        SELECT
            transaction_id,
            customer_id,
            amount,
            location,
            transaction_type,
            fraud_probability,
            risk_level
        FROM fraud_transactions
        WHERE predicted_fraud = 1
        ORDER BY fraud_probability DESC, amount DESC
        LIMIT %s
    """, (limit,))


def fraud_by_location():

    return run_query("""
        SELECT
            location,
            COUNT(*) AS total_transactions,
            COUNT(*) FILTER (
                WHERE predicted_fraud = 1
            ) AS suspected_fraud,
            COALESCE(SUM(amount) FILTER (
                WHERE predicted_fraud = 1
            ), 0) AS fraud_exposure
        FROM fraud_transactions
        GROUP BY location
        ORDER BY suspected_fraud DESC
    """)


def investigate_customer(customer_id):

    return run_query("""
        SELECT
            customer_id,
            amount,
            transaction_type,
            merchant_category,
            location,
            predicted_fraud,
            fraud_probability,
            risk_level,
            transaction_timestamp
        FROM fraud_transactions
        WHERE customer_id = %s
        ORDER BY transaction_timestamp DESC
        LIMIT 100
    """, (customer_id,))


def fraud_exposure():

    df = run_query("""
        SELECT COALESCE(SUM(amount), 0) AS exposure
        FROM fraud_transactions
        WHERE predicted_fraud = 1
    """)

    exposure = df.iloc[0]["exposure"]

    return (
        f"Total potential fraud exposure is "
        f"**${exposure:,.2f}**."
    )


def ask_assistant(question):

    question = question.lower().strip()

    customer = re.search(r"cust\d+", question)

    if customer:
        return investigate_customer(
            customer.group().upper()
        )

    if "today" in question:
        return (
            "Date-specific analysis is not supported yet. "
            "Try asking for an overall fraud summary."
        )

    if any(word in question for word in [
        "city", "cities", "location", "geographic"
    ]):
        return fraud_by_location()

    if any(word in question for word in [
        "exposure", "potential loss"
    ]):
        return fraud_exposure()

    if any(word in question for word in [
        "highest", "high risk", "high-risk",
        "suspicious", "top"
    ]):
        number = re.search(r"\b\d+\b", question)

        limit = int(number.group()) if number else 10
        limit = max(1, min(limit, 100))

        return highest_risk_transactions(limit)

    if any(word in question for word in [
        "summary", "overview", "total",
        "statistics", "fraud rate"
    ]):
        return fraud_summary()

    return """
I can help you investigate banking transactions.

Try asking:

- Show fraud summary
- Show top 10 suspicious transactions
- Which city has the most fraud?
- What is the potential fraud exposure?
- Investigate customer CUST1020
"""


if __name__ == "__main__":

    print("=== FRAUD INVESTIGATION ASSISTANT ===")
    print("Type exit to close the assistant.")

    while True:

        question = input("\nAsk a question: ")

        if question.lower().strip() == "exit":
            break

        try:
            response = ask_assistant(question)

            if isinstance(response, pd.DataFrame):
                if response.empty:
                    print("No matching transactions found.")
                else:
                    print(response.to_string(index=False))
            else:
                print(response)

        except Exception as error:
            print(f"Error: {error}")