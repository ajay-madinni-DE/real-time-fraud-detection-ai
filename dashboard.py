
import os
import re
import pandas as pd
import streamlit as st
import plotly.express as px

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from streamlit_autorefresh import st_autorefresh


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="AI Fraud Monitoring Center",
    page_icon="🛡️",
    layout="wide"
)


# =====================================================
# SESSION STATE
# =====================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# =====================================================
# DATABASE CONNECTION
# =====================================================

@st.cache_resource
def get_engine():

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER", "fraud_user"),
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5433")),
        database=os.getenv("DB_NAME", "fraud_detection")
    )

    return create_engine(
        url,
        pool_pre_ping=True
    )


def load_data():

    with get_engine().connect() as connection:

        return pd.read_sql(
            text("""
                SELECT *
                FROM fraud_transactions
                ORDER BY processed_at DESC
            """),
            connection
        )


# =====================================================
# DASHBOARD STYLING
# =====================================================

st.markdown("""
<style>

.stApp {
    background-color: #0b1120;
    color: #ffffff;
}

[data-testid="stMetric"] {
    background-color: #172033;
    border: 1px solid #334155;
    padding: 20px;
    border-radius: 15px;
}

[data-testid="stMetricValue"] {
    color: #38bdf8;
}

[data-testid="stMetricLabel"] {
    color: #e2e8f0;
}

[data-testid="stSidebar"] {
    background-color: #111827;
}

[data-testid="stSidebar"] * {
    color: #e2e8f0;
}

[data-testid="stChatMessage"] {
    background-color: #172033;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 10px;
}

h1, h2, h3 {
    color: #f8fafc;
}

.stButton > button {
    background-color: #1e293b;
    color: #ffffff;
    border: 1px solid #475569;
    border-radius: 8px;
}

.stButton > button:hover {
    border-color: #38bdf8;
    color: #38bdf8;
}
/* Fix investigation assistant text visibility */
[data-testid="stChatMessage"] {
    background-color: #172033 !important;
    color: #f8fafc !important;
}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3,
[data-testid="stChatMessage"] strong,
[data-testid="stChatMessage"] span {
    color: #f8fafc !important;
}

[data-testid="stChatInput"] textarea {
    color: #111827 !important;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# DASHBOARD HEADER
# =====================================================

st.title("🛡️ AI Fraud Monitoring Center")

st.caption(
    "Real-Time Banking Transaction Intelligence | "
    "Apache Kafka • Apache Spark • Machine Learning"
)


# =====================================================
# SIDEBAR NAVIGATION
# =====================================================

st.sidebar.title("Monitoring Center")

page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Live Dashboard",
        "🤖 Fraud Investigation Assistant"
    ]
)

auto_refresh = st.sidebar.toggle(
    "Automatic Refresh",
    value=True
)

# Pause automatic refresh on the chatbot page
# so users can type questions without interruption.

if auto_refresh and page == "📊 Live Dashboard":

    st_autorefresh(
        interval=5000,
        key="fraud_refresh"
    )


# =====================================================
# LOAD TRANSACTIONS
# =====================================================

try:

    df = load_data()

except Exception:

    st.error(
        "Database connection failed. "
        "Check the database configuration and password."
    )

    st.stop()


if df.empty:

    st.warning("Waiting for incoming transactions...")

    st.stop()


df["amount"] = pd.to_numeric(df["amount"])

df["fraud_probability"] = pd.to_numeric(
    df["fraud_probability"]
)

df["transaction_timestamp"] = pd.to_datetime(
    df["transaction_timestamp"],
    utc=True
)

df["status"] = df["predicted_fraud"].map({
    0: "Legitimate",
    1: "Suspected Fraud"
})


# =====================================================
# FRAUD INVESTIGATION CHATBOT
# =====================================================

def investigate(question, data):

    question_lower = question.lower().strip()

    suspected = data[
        data["predicted_fraud"] == 1
    ].copy()

    total = len(data)

    fraud_count = len(suspected)

    legitimate_count = total - fraud_count

    fraud_rate = (
        fraud_count / total * 100
        if total else 0
    )

    fraud_exposure = suspected["amount"].sum()

    total_value = data["amount"].sum()


    # -------------------------------------------------
    # CUSTOMER INVESTIGATION
    # -------------------------------------------------

    customer_match = re.search(
        r"\bCUST\d+\b",
        question,
        re.IGNORECASE
    )

    if customer_match:

        customer_id = customer_match.group().upper()

        customer_data = data[
            data["customer_id"] == customer_id
        ]

        if customer_data.empty:

            return (
                f"No matching transactions found "
                f"for customer **{customer_id}**."
            )

        customer_fraud = customer_data[
            customer_data["predicted_fraud"] == 1
        ]

        response = (
            f"### Customer Investigation: {customer_id}\n\n"
            f"- Total transactions: {len(customer_data):,}\n"
            f"- Suspected fraud: {len(customer_fraud):,}\n"
            f"- Total transaction value: "
            f"${customer_data['amount'].sum():,.2f}\n"
            f"- Potential fraud exposure: "
            f"${customer_fraud['amount'].sum():,.2f}\n\n"
            "**Transaction Details**"
        )

        columns = [
            "customer_id",
            "amount",
            "transaction_type",
            "merchant_category",
            "location",
            "predicted_fraud",
            "fraud_probability",
            "risk_level",
            "transaction_timestamp"
        ]

        return response, customer_data[columns]


    # -------------------------------------------------
    # TOP SUSPICIOUS TRANSACTIONS
    # -------------------------------------------------

    elif (
        "top" in question_lower
        and (
            "fraud" in question_lower
            or "suspicious" in question_lower
        )
    ):

        number_match = re.search(
            r"top\s+(\d+)",
            question_lower
        )

        limit = (
            min(max(int(number_match.group(1)), 1), 100)
            if number_match else 10
        )

        top_fraud = suspected.sort_values(
            "fraud_probability",
            ascending=False
        ).head(limit)

        columns = [
            "transaction_id",
            "customer_id",
            "amount",
            "location",
            "transaction_type",
            "fraud_probability",
            "risk_level"
        ]

        return (
            f"### Top {limit} Suspicious Transactions\n\n"
            "Ranked by predicted fraud probability.",
            top_fraud[columns]
        )


    # -------------------------------------------------
    # FRAUD BY LOCATION
    # -------------------------------------------------

    elif any(
        word in question_lower
        for word in [
            "city",
            "cities",
            "location",
            "geographic"
        ]
    ):

        location_data = (
            data.groupby("location")
            .agg(
                total_transactions=(
                    "transaction_id", "count"
                ),
                suspected_fraud=(
                    "predicted_fraud", "sum"
                )
            )
            .reset_index()
        )

        exposure = (
            suspected.groupby("location")["amount"]
            .sum()
            .reset_index(name="fraud_exposure")
        )

        location_data = location_data.merge(
            exposure,
            on="location",
            how="left"
        )

        location_data["fraud_exposure"] = (
            location_data["fraud_exposure"].fillna(0)
        )

        location_data = location_data.sort_values(
            "suspected_fraud",
            ascending=False
        )

        if fraud_count == 0:

            response = (
                "### Geographic Fraud Analysis\n\n"
                "No suspected fraud has been detected."
            )

        else:

            top_city = location_data.iloc[0]

            response = (
                "### Geographic Fraud Analysis\n\n"
                f"**{top_city['location']}** is among "
                "the locations with the highest number "
                "of suspected fraud transactions.\n\n"
                f"- Suspected fraud: "
                f"{int(top_city['suspected_fraud'])}\n"
                f"- Potential exposure: "
                f"${top_city['fraud_exposure']:,.2f}"
            )

        return response, location_data


    # -------------------------------------------------
    # FRAUD EXPOSURE
    # -------------------------------------------------

    elif any(
        word in question_lower
        for word in [
            "exposure",
            "potential loss",
            "financial risk"
        ]
    ):

        return (
            "### Potential Fraud Exposure\n\n"
            f"**${fraud_exposure:,.2f}**\n\n"
            f"This represents the total value of "
            f"{fraud_count:,} transactions flagged "
            "by the machine learning model.\n\n"
            "This is potential exposure, "
            "not confirmed financial loss."
        )


    # -------------------------------------------------
    # HIGH RISK TRANSACTIONS
    # -------------------------------------------------

    elif (
        "high risk" in question_lower
        or "high-risk" in question_lower
    ):

        high_risk = data[
            data["risk_level"] == "HIGH"
        ].sort_values(
            "fraud_probability",
            ascending=False
        )

        columns = [
            "customer_id",
            "amount",
            "location",
            "fraud_probability",
            "risk_level"
        ]

        return (
            "### High-Risk Transactions\n\n"
            f"Total high-risk transactions: "
            f"**{len(high_risk):,}**\n\n"
            "Showing up to 50 records.",
            high_risk[columns].head(50)
        )


    # -------------------------------------------------
    # MACHINE LEARNING PERFORMANCE
    # -------------------------------------------------

    elif any(
        word in question_lower
        for word in [
            "accuracy",
            "performance",
            "false positive",
            "missed fraud",
            "model"
        ]
    ):

        accuracy = (
            (
                data["is_fraud"]
                == data["predicted_fraud"]
            ).mean() * 100
            if total else 0
        )

        tp = len(data[
            (data["is_fraud"] == 1)
            & (data["predicted_fraud"] == 1)
        ])

        fp = len(data[
            (data["is_fraud"] == 0)
            & (data["predicted_fraud"] == 1)
        ])

        fn = len(data[
            (data["is_fraud"] == 1)
            & (data["predicted_fraud"] == 0)
        ])

        precision = (
            tp / (tp + fp) * 100
            if tp + fp else 0
        )

        recall = (
            tp / (tp + fn) * 100
            if tp + fn else 0
        )

        return (
            "### Machine Learning Performance\n\n"
            f"- Prediction accuracy: {accuracy:.2f}%\n"
            f"- Precision: {precision:.2f}%\n"
            f"- Recall: {recall:.2f}%\n"
            f"- True positives: {tp:,}\n"
            f"- False positives: {fp:,}\n"
            f"- Missed fraud: {fn:,}\n\n"
            "These metrics are calculated using "
            "synthetic fraud labels and do not "
            "establish real-world model accuracy."
        )


    # -------------------------------------------------
    # FRAUD SUMMARY
    # -------------------------------------------------

    elif any(
        word in question_lower
        for word in [
            "summary",
            "overview",
            "total",
            "statistics",
            "report",
            "fraud rate"
        ]
    ):

        return (
            "### Fraud Investigation Summary\n\n"
            f"- Total transactions: {total:,}\n"
            f"- Suspected fraud: {fraud_count:,}\n"
            f"- Predicted legitimate: "
            f"{legitimate_count:,}\n"
            f"- Fraud flag rate: {fraud_rate:.2f}%\n"
            f"- Total transaction value: "
            f"${total_value:,.2f}\n"
            f"- Potential fraud exposure: "
            f"${fraud_exposure:,.2f}\n\n"
            "**Recommendation:** Review high-risk "
            "transactions before taking any action."
        )


    # -------------------------------------------------
    # DEFAULT RESPONSE
    # -------------------------------------------------

    else:

        return (
            "I can help investigate banking transactions.\n\n"
            "Try asking:\n\n"
            "- Show fraud summary\n"
            "- Show top 10 suspicious transactions\n"
            "- Which city has the most fraud?\n"
            "- What is the potential fraud exposure?\n"
            "- Show high-risk transactions\n"
            "- Investigate customer CUST4446\n"
            "- Show model performance"
        )


# =====================================================
# CHATBOT USER INTERFACE
# =====================================================

def render_assistant():

    st.subheader("🤖 Fraud Investigation Assistant")

    st.success(
        "● Database connected | "
        "Investigation assistant ready"
    )

    st.caption(
        "Rule-based investigation assistant using "
        "live PostgreSQL transaction data."
    )

    st.info(
        "Ask questions about suspicious transactions, "
        "customer activity, geographic fraud patterns, "
        "financial exposure and model performance. "
        "The assistant searches all stored transactions."
    )

    left, right = st.columns([3, 1])

    with left:

        st.caption(
            f"Database snapshot: {len(df):,} transactions"
        )

        st.button(
            "🔄 Refresh Transaction Data",
            key="refresh_assistant"
        )

    with right:

        if st.button("🗑️ Clear Chat"):

            st.session_state.chat_history = []

            st.rerun()


    st.markdown("#### Suggested Investigation Questions")

    col1, col2, col3 = st.columns(3)

    selected_question = None

    with col1:

        if st.button(
            "📊 Fraud Summary",
            width="stretch"
        ):

            selected_question = "Show fraud summary"

        if st.button(
            "🚨 High-Risk Transactions",
            width="stretch"
        ):

            selected_question = (
                "Show high-risk transactions"
            )

    with col2:

        if st.button(
            "🔍 Top 10 Suspicious",
            width="stretch"
        ):

            selected_question = (
                "Show top 10 suspicious transactions"
            )

        if st.button(
            "🤖 Model Performance",
            width="stretch"
        ):

            selected_question = (
                "Show model performance"
            )

    with col3:

        if st.button(
            "🌎 Fraud by Location",
            width="stretch"
        ):

            selected_question = (
                "Which city has the most fraud?"
            )

        if st.button(
            "💰 Fraud Exposure",
            width="stretch"
        ):

            selected_question = (
                "What is the potential fraud exposure?"
            )


    st.divider()


    # Display previous chat messages

    for message in st.session_state.chat_history:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message.get("table") is not None:

                st.dataframe(
                    message["table"],
                    width="stretch",
                    hide_index=True
                )


    # Accept a new investigation question

    typed_question = st.chat_input(
        "Ask a fraud investigation question..."
    )

    question = typed_question or selected_question


    if question:

        st.session_state.chat_history.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):

            st.markdown(question)


        with st.chat_message("assistant"):

            with st.spinner(
                "Analyzing banking transactions..."
            ):

                result = investigate(question, df)

                if isinstance(result, tuple):

                    response, table = result

                else:

                    response = result

                    table = None


            st.markdown(response)

            if table is not None:

                st.dataframe(
                    table,
                    width="stretch",
                    hide_index=True
                )


            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response,
                "table": table
            })


    st.divider()

    st.caption(
        "Investigation results are based on simulated "
        "banking data and machine learning predictions. "
        "Human review is required before taking action."
    )


# =====================================================
# ASSISTANT PAGE ROUTING
# =====================================================

if page == "🤖 Fraud Investigation Assistant":

    render_assistant()

    st.stop()


# =====================================================
# LIVE DASHBOARD
# =====================================================

st.success(
    "● Database connected | "
    + (
        "Auto-refresh enabled"
        if auto_refresh
        else "Auto-refresh paused"
    )
)


# =====================================================
# DASHBOARD FILTERS
# =====================================================

st.sidebar.divider()

st.sidebar.title("Dashboard Filters")

risk_options = ["HIGH", "MEDIUM", "LOW"]

selected_risks = st.sidebar.multiselect(
    "Risk Level",
    risk_options,
    default=risk_options
)

locations = sorted(
    df["location"].dropna().unique().tolist()
)

selected_locations = st.sidebar.multiselect(
    "Location",
    locations,
    default=locations
)

filtered_df = df[
    df["risk_level"].isin(selected_risks)
    & df["location"].isin(selected_locations)
].copy()


# =====================================================
# CALCULATE DASHBOARD METRICS
# =====================================================

total_transactions = len(filtered_df)

fraud_df = filtered_df[
    filtered_df["predicted_fraud"] == 1
]

fraud_count = len(fraud_df)

legitimate_count = total_transactions - fraud_count

fraud_rate = (
    fraud_count / total_transactions * 100
    if total_transactions else 0
)

total_amount = filtered_df["amount"].sum()

fraud_amount = fraud_df["amount"].sum()


# =====================================================
# KPI CARDS
# =====================================================

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Transactions",
    f"{total_transactions:,}"
)

col2.metric(
    "Suspected Fraud",
    f"{fraud_count:,}"
)

col3.metric(
    "Legitimate Transactions",
    f"{legitimate_count:,}"
)

col4, col5, col6 = st.columns(3)

col4.metric(
    "Fraud Flag Rate",
    f"{fraud_rate:.2f}%"
)

col5.metric(
    "Total Transaction Value",
    f"${total_amount:,.2f}"
)

col6.metric(
    "Potential Fraud Exposure",
    f"${fraud_amount:,.2f}"
)

st.divider()


# =====================================================
# CHART STYLING
# =====================================================

def display_chart(fig):

    fig.update_layout(
        paper_bgcolor="#0b1120",
        plot_bgcolor="#111827",
        font_color="#e2e8f0",
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20
        )
    )

    st.plotly_chart(
        fig,
        width="stretch",
        theme=None
    )


# =====================================================
# TRANSACTION ACTIVITY
# =====================================================

st.subheader("📈 Real-Time Transaction Activity")

timeline = (
    filtered_df
    .assign(
        minute=filtered_df[
            "transaction_timestamp"
        ].dt.floor("min")
    )
    .groupby("minute")
    .agg(
        transactions=("transaction_id", "count"),
        suspected_fraud=("predicted_fraud", "sum")
    )
    .reset_index()
)

fig = px.line(
    timeline,
    x="minute",
    y=["transactions", "suspected_fraud"],
    markers=True,
    template="plotly_dark",
    color_discrete_sequence=[
        "#38bdf8",
        "#ef4444"
    ],
    labels={
        "minute": "Time (UTC)",
        "value": "Transactions",
        "variable": "Category"
    }
)

display_chart(fig)


# =====================================================
# DISTRIBUTION CHARTS
# =====================================================

left, right = st.columns(2)

with left:

    st.subheader("Transaction Distribution")

    distribution = (
        filtered_df["status"]
        .value_counts()
        .rename_axis("status")
        .reset_index(name="count")
    )

    fig = px.pie(
        distribution,
        names="status",
        values="count",
        hole=0.55,
        template="plotly_dark",
        color="status",
        color_discrete_map={
            "Legitimate": "#22c55e",
            "Suspected Fraud": "#ef4444"
        }
    )

    display_chart(fig)


with right:

    st.subheader("Risk Level Distribution")

    risks = (
        filtered_df["risk_level"]
        .value_counts()
        .rename_axis("risk")
        .reset_index(name="count")
    )

    fig = px.bar(
        risks,
        x="risk",
        y="count",
        color="risk",
        template="plotly_dark",
        color_discrete_map={
            "HIGH": "#ef4444",
            "MEDIUM": "#f59e0b",
            "LOW": "#22c55e"
        }
    )

    display_chart(fig)


# =====================================================
# LOCATION AND MERCHANT ANALYTICS
# =====================================================

left, right = st.columns(2)

with left:

    st.subheader("🌎 Fraud by Location")

    location_fraud = (
        fraud_df.groupby("location")
        .size()
        .reset_index(name="fraud_count")
    )

    fig = px.bar(
        location_fraud,
        x="location",
        y="fraud_count",
        template="plotly_dark",
        color_discrete_sequence=["#ef4444"]
    )

    display_chart(fig)


with right:

    st.subheader("Transaction Value by Merchant")

    merchant_data = (
        filtered_df.groupby(
            "merchant_category"
        )["amount"]
        .sum()
        .reset_index()
    )

    fig = px.bar(
        merchant_data,
        x="merchant_category",
        y="amount",
        template="plotly_dark",
        color_discrete_sequence=["#38bdf8"]
    )

    display_chart(fig)


# =====================================================
# FRAUD ALERTS
# =====================================================

st.divider()

st.subheader("🚨 Recent Fraud Alerts")

alert_columns = [
    "customer_id",
    "amount",
    "transaction_type",
    "merchant_category",
    "location",
    "fraud_probability",
    "risk_level",
    "transaction_timestamp"
]

if fraud_df.empty:

    st.info(
        "No suspected fraud in the selected records."
    )

else:

    st.dataframe(
        fraud_df[alert_columns].head(20),
        width="stretch",
        hide_index=True,
        column_config={
            "amount": st.column_config.NumberColumn(
                "Amount ($)",
                format="$%.2f"
            ),
            "fraud_probability":
                st.column_config.ProgressColumn(
                    "Fraud Probability",
                    min_value=0,
                    max_value=1,
                    format="%.3f"
                )
        }
    )


# =====================================================
# MACHINE LEARNING PERFORMANCE
# =====================================================

st.divider()

st.subheader("🤖 Machine Learning Performance")

accuracy = (
    (
        filtered_df["is_fraud"]
        == filtered_df["predicted_fraud"]
    ).mean() * 100
    if total_transactions else 0
)

true_positives = len(filtered_df[
    (filtered_df["is_fraud"] == 1)
    & (filtered_df["predicted_fraud"] == 1)
])

false_positives = len(filtered_df[
    (filtered_df["is_fraud"] == 0)
    & (filtered_df["predicted_fraud"] == 1)
])

false_negatives = len(filtered_df[
    (filtered_df["is_fraud"] == 1)
    & (filtered_df["predicted_fraud"] == 0)
])

m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Prediction Accuracy",
    f"{accuracy:.2f}%"
)

m2.metric(
    "True Positives",
    true_positives
)

m3.metric(
    "False Positives",
    false_positives
)

m4.metric(
    "Missed Fraud",
    false_negatives
)

st.caption(
    "Performance is measured against synthetic fraud "
    "labels. It does not establish real-world banking "
    "model accuracy."
)


# =====================================================
# RECENT TRANSACTIONS
# =====================================================

st.divider()

st.subheader("📋 Recent Banking Transactions")

st.dataframe(
    filtered_df.head(100),
    width="stretch",
    hide_index=True
)


# =====================================================
# DOWNLOAD INVESTIGATION REPORT
# =====================================================

st.download_button(
    label="📥 Download Fraud Investigation Report",
    data=fraud_df.to_csv(index=False),
    file_name="fraud_investigation_report.csv",
    mime="text/csv"
)


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "AI Fraud Detection System | "
    "Kafka + Spark + Random Forest + PostgreSQL "
    "+ Streamlit + Investigation Assistant"
)
