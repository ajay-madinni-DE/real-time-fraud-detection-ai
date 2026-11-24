
import os
import joblib
import pandas as pd
import pytest

from fraud_model import generate_training_data, MODEL_PATH


@pytest.fixture(scope="module")
def model():
    return joblib.load(MODEL_PATH)


def create_transaction(amount, international=False):
    return pd.DataFrame([{
        "amount": amount,
        "transaction_type": "DEBIT",
        "merchant_category": "Retail",
        "location": "Charlotte",
        "is_international": international
    }])


def test_training_data_generation():
    data = generate_training_data(1000)

    assert len(data) == 1000
    assert not data.isnull().any().any()


def test_training_data_columns():
    data = generate_training_data(100)

    expected_columns = {
        "amount",
        "transaction_type",
        "merchant_category",
        "location",
        "is_international",
        "is_fraud"
    }

    assert set(data.columns) == expected_columns


def test_training_data_labels():
    data = generate_training_data(1000)

    assert set(data["is_fraud"].unique()) == {0, 1}


def test_model_file_exists():
    assert os.path.isfile(MODEL_PATH)


def test_model_loading(model):
    assert hasattr(model, "predict")
    assert hasattr(model, "predict_proba")


def test_legitimate_transaction(model):
    transaction = create_transaction(150.00)

    prediction = model.predict(transaction)[0]

    assert prediction == 0


def test_fraudulent_transaction(model):
    transaction = create_transaction(
        20000.00,
        international=True
    )

    prediction = model.predict(transaction)[0]

    assert prediction == 1


def test_prediction_probability(model):
    transaction = create_transaction(10000.00, True)

    probabilities = model.predict_proba(transaction)[0]

    assert all(0 <= value <= 1 for value in probabilities)
    assert sum(probabilities) == pytest.approx(1.0)


def test_unknown_location(model):
    transaction = create_transaction(150.00)

    transaction["location"] = "Boston"

    prediction = model.predict(transaction)[0]

    assert prediction in [0, 1]
