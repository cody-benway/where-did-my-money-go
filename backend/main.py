import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import io
import os
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
    history: List[ChatMessage] = []


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_transactions(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV.")

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File is too large. Please upload a CSV under 5 MB.")

    try:
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {str(e)}")

    df.columns = df.columns.str.lower().str.strip()

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(sorted(missing))}. "
                   f"Expected columns: date, description, amount, category."
        )

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if df["amount"].isna().all():
        raise HTTPException(
            status_code=400,
            detail="The 'amount' column could not be parsed as numbers. "
                   "Make sure amounts are numeric (e.g. -42.50, not '$42.50')."
        )

    total_spent = df[df["amount"] < 0]["amount"].sum()
    total_income = df[df["amount"] > 0]["amount"].sum()
    by_category = df[df["amount"] < 0].groupby("category")["amount"].sum().abs().to_dict()
    top_merchants = df[df["amount"] < 0].groupby("description")["amount"].sum().nsmallest(5).abs().to_dict()

    summary = f"""
    Here is a summary of a user's financial transactions:
    - Total income: ${total_income:.2f}
    - Total spent: ${abs(total_spent):.2f}
    - Spending by category: {by_category}
    - Top 5 merchants by spending: {top_merchants}
    
    Please write a friendly, conversational 3-4 paragraph narrative analyzing this person's 
    spending. Highlight patterns, call out any notable categories, compare income to spending, 
    and offer 2-3 practical and specific suggestions for where they could cut back. 
    Keep the tone helpful and non-judgmental.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=summary
        )
        narrative = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")

    df["date"] = pd.to_datetime(df["date"])
    daily_spending = (
        df[df["amount"] < 0]
        .groupby(df["date"].dt.strftime("%m/%d"))["amount"]
        .sum()
        .abs()
        .reset_index()
        .to_dict(orient="records")
    )

    return {
        "narrative": narrative,
        "transactions": df.to_dict(orient="records"),
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

    system_context = f"""You are a helpful personal finance assistant. 
    The user has uploaded their transaction data. Answer questions about their spending clearly and concisely.

    Check if the user has uploaded their transaction data. If they have, use the transaction data to answer the question. If they have not, ask them to upload their transaction data in the system; they cannot upload their transaction data in the chat. If they try to upload their transaction data in the chat, ask them to upload it in the system so you can fully analyze their spending and answer their question.
    
    Transaction data:
    {transactions_text}
    """

    contents = []
    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": request.question}]})

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
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
