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

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    transactions: list
    history: List[ChatMessage] = []

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/upload")
async def upload_transactions(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    contents = await file.read()
    
    try:
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {str(e)}")
    
    df.columns = df.columns.str.lower().str.strip()

    return {
        "rows": len(df),
        "columns": list(df.columns),
        "preview": df.head(5).to_dict(orient="records")
    }

@app.post("/analyze")
async def analyze_transactions(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()

    try:
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {str(e)}")

    df.columns = df.columns.str.lower().str.strip()

    total_spent = df[df["amount"] < 0]["amount"].sum()
    total_income = df[df["amount"] > 0]["amount"].sum()
    by_category = df[df["amount"] < 0].groupby("category")["amount"].sum().to_dict()
    top_merchants = df[df["amount"] < 0].groupby("description")["amount"].sum().nsmallest(5).to_dict()

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
    
    Transaction data:
    {transactions_text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=system_context + "\n\nUser question: " + request.question
        )
        return {"answer": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")