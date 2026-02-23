import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import io
import os
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from jinja2 import Environment, FileSystemLoader

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

prompts_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "prompts")),
    trim_blocks=True,
    lstrip_blocks=True,
)

app = FastAPI(title="Where Did My Money Go API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
REQUIRED_COLUMNS = {"date", "description", "amount", "category"}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    transactions: list = []
    stats: dict = {}
    history: List[ChatMessage] = []


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_transactions(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one CSV file.")

    frames = []
    for file in files:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail=f'"{file.filename}" is not a CSV file. All files must be CSVs.')

        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f'"{file.filename}" is too large. Each file must be under 5 MB.')

        try:
            frame = pd.read_csv(io.StringIO(contents.decode("utf-8")))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'Could not parse "{file.filename}": {str(e)}')

        frame.columns = frame.columns.str.lower().str.strip()

        missing = REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f'"{file.filename}" is missing required columns: {", ".join(sorted(missing))}. '
                       f"Expected columns: date, description, amount, category."
            )

        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
        if frame["amount"].isna().all():
            raise HTTPException(
                status_code=400,
                detail=f'The "amount" column in "{file.filename}" could not be parsed as numbers. '
                       "Make sure amounts are numeric (e.g. -42.50, not '$42.50')."
            )

        frames.append(frame)

    df = pd.concat(frames, ignore_index=True).drop_duplicates()

    if df["amount"].isna().all():
        raise HTTPException(status_code=400, detail="No valid numeric amounts found across the uploaded files.")

    total_spent = df[df["amount"] < 0]["amount"].sum()
    total_income = df[df["amount"] > 0]["amount"].sum()
    by_category = df[df["amount"] < 0].groupby("category")["amount"].sum().abs().to_dict()
    top_merchants = df[df["amount"] < 0].groupby("description")["amount"].sum().nsmallest(5).abs().to_dict()

    df["date"] = pd.to_datetime(df["date"])
    daily_spending = (
        df[df["amount"] < 0]
        .groupby(df["date"].dt.strftime("%m/%d"))["amount"]
        .sum()
        .abs()
        .reset_index()
        .to_dict(orient="records")
    )

    # Multi-period trend computation (weekly, monthly, quarterly, yearly)
    spending_df = df[df["amount"] < 0].copy()

    def build_period_data(grouped_df, period_col, label_fn):
        """
        Build all_periods list, spending map, default trends, and default labels
        for a given period granularity.
        """
        # Collect all unique periods in sorted order
        all_period_keys = sorted(grouped_df[period_col].unique())
        all_periods = [label_fn(p) for p in all_period_keys]

        # Build spending map: { "Jan 2025": { "Dining": 120.50, ... }, ... }
        spending = {}
        for p_key, label in zip(all_period_keys, all_periods):
            period_rows = grouped_df[grouped_df[period_col] == p_key]
            spending[label] = {
                row["category"]: round(float(row["amount"]), 2)
                for _, row in period_rows.iterrows()
            }

        # Default: compare two most recent periods
        default_trends = {}
        default_labels = None
        if len(all_periods) >= 2:
            prev_label = all_periods[-2]
            curr_label = all_periods[-1]
            default_labels = [prev_label, curr_label]
            for category in by_category:
                prev_amt = spending[prev_label].get(category, 0)
                curr_amt = spending[curr_label].get(category, 0)
                if prev_amt > 0:
                    change_pct = ((curr_amt - prev_amt) / prev_amt) * 100
                    default_trends[category] = {
                        "change_pct": round(abs(change_pct), 1),
                        "direction": "up" if change_pct > 0 else "down",
                    }

        return {
            "trends": default_trends,
            "labels": default_labels,
            "all_periods": all_periods,
            "spending": spending,
        }

    # Weekly
    spending_df["year_week"] = spending_df["date"].dt.to_period("W")
    weekly_by_cat = spending_df.groupby(["year_week", "category"])["amount"].sum().abs().reset_index()
    weekly_data = build_period_data(weekly_by_cat, "year_week", lambda p: f"Wk of {p.start_time.strftime('%b %d')}")

    # Monthly
    spending_df["year_month"] = spending_df["date"].dt.to_period("M")
    monthly_by_cat = spending_df.groupby(["year_month", "category"])["amount"].sum().abs().reset_index()
    monthly_data = build_period_data(monthly_by_cat, "year_month", lambda p: p.strftime("%b %Y"))

    # Quarterly
    spending_df["year_quarter"] = spending_df["date"].dt.to_period("Q")
    quarterly_by_cat = spending_df.groupby(["year_quarter", "category"])["amount"].sum().abs().reset_index()
    quarterly_data = build_period_data(quarterly_by_cat, "year_quarter", lambda p: f"Q{p.quarter} {p.year}")

    # Yearly
    spending_df["year"] = spending_df["date"].dt.to_period("Y")
    yearly_by_cat = spending_df.groupby(["year", "category"])["amount"].sum().abs().reset_index()
    yearly_data = build_period_data(yearly_by_cat, "year", lambda p: str(p.year))

    trends_by_period = {
        "Weekly":    weekly_data,
        "Monthly":   monthly_data,
        "Quarterly": quarterly_data,
        "Yearly":    yearly_data,
    }

    # Use monthly trends for the AI narrative summary
    monthly_trends = monthly_data["trends"]
    trends_summary = ", ".join(
        f"{cat}: {t['direction']} {t['change_pct']}%" for cat, t in monthly_trends.items()
    ) if monthly_trends else "Not enough data for month-over-month trends"

    date_range_start = df["date"].min().strftime("%B %d, %Y")
    date_range_end = df["date"].max().strftime("%B %d, %Y")

    analyze_system = prompts_env.get_template("analyze_system.j2").render()
    analyze_user = prompts_env.get_template("analyze_user.j2").render(
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        total_income=f"{total_income:.2f}",
        total_spent=f"{abs(total_spent):.2f}",
        by_category=by_category,
        top_merchants=top_merchants,
        trends_summary=trends_summary,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=analyze_user,
            config={"system_instruction": analyze_system},
        )
        narrative = response.text
    except Exception:
        narrative = None

    return {
        "narrative": narrative,
        "transactions": df.to_dict(orient="records"),
        "trends_by_period": trends_by_period,
        "stats": {
            "total_income": total_income,
            "total_spent": abs(total_spent),
            "by_category": by_category,
            "top_merchants": top_merchants,
            "daily_spending": daily_spending
        }
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    transactions_text = "\n".join([
        f"{t.get('date')} | {t.get('description')} | ${t.get('amount')} | {t.get('category')}"
        for t in request.transactions
    ])

    system_context = prompts_env.get_template("chat_system.j2").render()
    transaction_context = prompts_env.get_template("chat_user.j2").render(
        transactions_text=transactions_text,
        stats=request.stats,
    )

    contents = []
    if transactions_text:
        contents.append({"role": "user", "parts": [{"text": transaction_context}]})
        contents.append({"role": "model", "parts": [{"text": "Got it, I have your transaction data loaded and ready."}]})
    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": request.question}]})

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=contents,
            config={"system_instruction": system_context}
        )
        return {"answer": response.text}
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(
                status_code=429,
                detail="The AI service has reached its daily request limit. Please try again tomorrow or upgrade your Gemini API plan."
            )
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")
