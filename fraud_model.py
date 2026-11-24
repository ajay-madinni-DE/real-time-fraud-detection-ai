
import os
import random
import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

random.seed(42)

MODEL_PATH = "models/fraud_model.pkl"
DATA_PATH = "data/training_transactions.csv"

LOCATIONS = [
    "New York", "Charlotte", "Dallas",
    "Chicago", "Miami", "Seattle"
]

MERCHANTS = [
    "Retail", "Travel", "Grocery",
    "Electronics", "Restaurant", "Online"
]


def generate_training_data(records=20000):

    transactions = []

    for _ in range(records):

        suspicious = random.random() < 0.05

        if suspicious:
            amount = round(random.uniform(5000, 25000), 2)
        else:
            amount = round(random.uniform(5, 2000), 2)

        transactions.append({
            "amount": amount,
            "transaction_type": random.choice(
                ["DEBIT", "CREDIT", "TRANSFER"]
            ),
            "merchant_category": random.choice(MERCHANTS),
            "location": random.choice(LOCATIONS),
            "is_international": random.random() < (
                0.8 if suspicious else 0.05
            ),
            "is_fraud": int(suspicious)
        })

    return pd.DataFrame(transactions)


def train_model():

    print("=== FRAUD DETECTION MODEL TRAINING ===")

    os.makedirs("models", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    df = generate_training_data()

    df.to_csv(DATA_PATH, index=False)

    print(f"\nTotal transactions: {len(df)}")
    print(f"Fraud transactions: {df['is_fraud'].sum()}")
    print(f"Legitimate transactions: {(df['is_fraud'] == 0).sum()}")

    X = df.drop(columns=["is_fraud"])
    y = df["is_fraud"]

    categorical_features = [
        "transaction_type",
        "merchant_category",
        "location"
    ]

    numerical_features = [
        "amount",
        "is_international"
    ]

    preprocessor = ColumnTransformer([
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features
        ),
        (
            "numerical",
            "passthrough",
            numerical_features
        )
    ])

    model = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        ))
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    print("\nTraining Random Forest model...")

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    print("\n=== MODEL EVALUATION ===")

    print(f"Accuracy: {accuracy_score(y_test, predictions):.2%}")

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, predictions))

    print("\nClassification Report:")
    print(classification_report(y_test, predictions))

    joblib.dump(model, MODEL_PATH)

    print(f"\nTraining data saved: {DATA_PATH}")
    print(f"Model saved: {MODEL_PATH}")
    print("\nModel training completed successfully!")


if __name__ == "__main__":
    train_model()
