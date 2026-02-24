import json
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
import os
from google import genai
from google.genai import types
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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    transactions: list = []
    stats: dict = {}
    history: List[ChatMessage] = []


class NarrativeRequest(BaseModel):
    stats: dict
    date_range_start: str
    date_range_end: str
    trends_summary: str


# ---------------------------------------------------------------------------
# Tool definitions for function calling
# ---------------------------------------------------------------------------

FINANCE_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_category_total",
            description="Returns the total amount spent in a specific spending category.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "category": types.Schema(
                        type=types.Type.STRING,
                        description="The name of the spending category (e.g. 'Dining', 'Groceries').",
                    )
                },
                required=["category"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_top_merchants",
            description="Returns the top merchants ranked by total spending.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "n": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of top merchants to return (default 5).",
                    )
                },
                required=[],
            ),
        ),
        types.FunctionDeclaration(
            name="find_transactions",
            description="Searches transactions by keyword in the description and optional amount range. Use expenses_only=true to restrict to spending transactions (debits) and exclude income.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "keyword": types.Schema(
                        type=types.Type.STRING,
                        description="Case-insensitive keyword to search in the transaction description.",
                    ),
                    "min_amount": types.Schema(
                        type=types.Type.NUMBER,
                        description="Minimum absolute transaction amount (optional).",
                    ),
                    "max_amount": types.Schema(
                        type=types.Type.NUMBER,
                        description="Maximum absolute transaction amount (optional).",
                    ),
                    "expenses_only": types.Schema(
                        type=types.Type.BOOLEAN,
                        description="If true, only return expense (debit/spending) transactions and exclude income. Default false.",
                    ),
                },
                required=[],
            ),
        ),
        types.FunctionDeclaration(
            name="get_largest_transactions",
            description="Returns the largest individual transactions sorted by amount. Use this when the user asks about their biggest purchase, largest expense, most expensive transaction, etc. Always set expenses_only=true unless the user explicitly asks about income.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "n": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of transactions to return (default 5).",
                    ),
                    "expenses_only": types.Schema(
                        type=types.Type.BOOLEAN,
                        description="If true, only consider expense (debit/spending) transactions and exclude income. Default true.",
                    ),
                },
                required=[],
            ),
        ),
    ]
)


def execute_tool(name: str, args: dict, transactions: list, stats: dict) -> str:
    """Execute a tool call and return a string result."""
    if name == "get_category_total":
        category = args.get("category", "")
        by_category = stats.get("by_category", {})
        # Case-insensitive lookup
        for cat, total in by_category.items():
            if cat.lower() == category.lower():
                return json.dumps({"category": cat, "total_spent": round(float(total), 2)})
        return json.dumps({"error": f"Category '{category}' not found.", "available_categories": list(by_category.keys())})

    elif name == "get_top_merchants":
        n = int(args.get("n", 5))
        top = stats.get("top_merchants", {})
        sorted_merchants = sorted(top.items(), key=lambda x: x[1], reverse=True)[:n]
        return json.dumps({"top_merchants": [{"merchant": m, "total_spent": round(float(v), 2)} for m, v in sorted_merchants]})

    elif name == "find_transactions":
        keyword = args.get("keyword", "").lower()
        min_amt = args.get("min_amount")
        max_amt = args.get("max_amount")
        expenses_only = args.get("expenses_only", False)
        results = []
        for t in transactions:
            raw_amount = float(t.get("amount", 0))
            if expenses_only and raw_amount >= 0:
                continue
            desc = str(t.get("description", "")).lower()
            if keyword and keyword not in desc:
                continue
            amt = abs(raw_amount)
            if min_amt is not None and amt < min_amt:
                continue
            if max_amt is not None and amt > max_amt:
                continue
            results.append({
                "date": str(t.get("date", "")),
                "description": t.get("description", ""),
                "amount": round(raw_amount, 2),
                "category": t.get("category", ""),
            })
        return json.dumps({"transactions": results[:50], "total_found": len(results)})

    elif name == "get_largest_transactions":
        n = int(args.get("n", 5))
        expenses_only = args.get("expenses_only", True)
        candidates = []
        for t in transactions:
            raw_amount = float(t.get("amount", 0))
            if expenses_only and raw_amount >= 0:
                continue
            candidates.append({
                "date": str(t.get("date", "")),
                "description": t.get("description", ""),
                "amount": round(raw_amount, 2),
                "category": t.get("category", ""),
            })
        # Sort by absolute amount descending
        candidates.sort(key=lambda x: abs(x["amount"]), reverse=True)
        return json.dumps({"largest_transactions": candidates[:n]})

    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Column mapping helper
# ---------------------------------------------------------------------------

COLUMN_MAPPING_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "date":        types.Schema(type=types.Type.STRING, description="Column name that maps to 'date'"),
        "description": types.Schema(type=types.Type.STRING, description="Column name that maps to 'description'"),
        "amount":      types.Schema(type=types.Type.STRING, description="Column name that maps to 'amount'"),
        "category":    types.Schema(type=types.Type.STRING, description="Column name that maps to 'category'"),
    },
    required=["date", "description", "amount", "category"],
)


def infer_column_mapping(headers: list[str], sample_rows: list[dict]) -> dict | None:
    """
    Ask Gemini to map actual CSV column names to the required schema fields.
    Returns a dict like {"date": "Trans Date", "amount": "Debit", ...} or None on failure.
    """
    prompt = prompts_env.get_template("column_mapping_user.j2").render(
        headers=headers,
        sample_rows=sample_rows,
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=COLUMN_MAPPING_SCHEMA,
            ),
        )
        mapping = json.loads(response.text)
        # Validate all mapped columns actually exist in the CSV
        for required_col, actual_col in mapping.items():
            if actual_col not in headers:
                return None
        return mapping
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Analyze endpoint
# ---------------------------------------------------------------------------

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
            # Attempt AI-powered column mapping before giving up
            headers = list(frame.columns)
            sample_rows = frame.head(3).to_dict(orient="records")
            mapping = infer_column_mapping(headers, sample_rows)

            if mapping:
                # Rename columns to the required names
                frame = frame.rename(columns={v: k for k, v in mapping.items()})
                # Re-check after mapping
                still_missing = REQUIRED_COLUMNS - set(frame.columns)
                if still_missing:
                    raise HTTPException(
                        status_code=400,
                        detail=f'"{file.filename}" is missing required columns: {", ".join(sorted(still_missing))}. '
                               f"Expected columns: date, description, amount, category."
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f'"{file.filename}" is missing required columns: {", ".join(sorted(missing))}. '
                           f"Expected columns: date, description, amount, category. "
                           f"AI column mapping was attempted but could not confidently identify the correct columns."
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
        .groupby(df["date"].dt.strftime("%m/%d/%Y"))["amount"]
        .sum()
        .abs()
        .reset_index()
        .to_dict(orient="records")
    )

    # Multi-period trend computation (weekly, monthly, quarterly, yearly)
    spending_df = df[df["amount"] < 0].copy()

    def build_period_data(grouped_df, period_col, label_fn):
        all_period_keys = sorted(grouped_df[period_col].unique())
        all_periods = [label_fn(p) for p in all_period_keys]

        spending = {}
        for p_key, label in zip(all_period_keys, all_periods):
            period_rows = grouped_df[grouped_df[period_col] == p_key]
            spending[label] = {
                row["category"]: round(float(row["amount"]), 2)
                for _, row in period_rows.iterrows()
            }

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

    return {
        "transactions": df.to_dict(orient="records"),
        "trends_by_period": trends_by_period,
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
        "trends_summary": trends_summary,
        "stats": {
            "total_income": total_income,
            "total_spent": abs(total_spent),
            "by_category": by_category,
            "top_merchants": top_merchants,
            "daily_spending": daily_spending
        }
    }


# ---------------------------------------------------------------------------
# Narrative endpoint
# ---------------------------------------------------------------------------

@app.post("/narrative")
async def generate_narrative(request: NarrativeRequest):
    analyze_system = prompts_env.get_template("analyze_system.j2").render()
    analyze_user = prompts_env.get_template("analyze_user.j2").render(
        date_range_start=request.date_range_start,
        date_range_end=request.date_range_end,
        total_income=f"{request.stats.get('total_income', 0):.2f}",
        total_spent=f"{request.stats.get('total_spent', 0):.2f}",
        by_category=request.stats.get("by_category", {}),
        top_merchants=request.stats.get("top_merchants", {}),
        trends_summary=request.trends_summary,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=analyze_user,
            config={"system_instruction": analyze_system},
        )
        return {"narrative": response.text}
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(status_code=429, detail="The AI service has reached its daily request limit. Please try again tomorrow or upgrade your Gemini API plan.")
        raise HTTPException(status_code=500, detail=f"Failed to generate narrative: {str(e)}")


# ---------------------------------------------------------------------------
# Chat (streaming) endpoint
# ---------------------------------------------------------------------------

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    transactions_text = "\n".join([
        f"{t.get('date')} | {t.get('description')} | ${t.get('amount')} | {t.get('category')}"
        for t in request.transactions
    ])

    system_context = prompts_env.get_template("chat_system.j2").render()
    transaction_context = prompts_env.get_template("chat_user.j2").render(
        transactions_text=transactions_text,
        stats=request.stats,
    )

    # Build conversation history
    contents = []
    if transactions_text:
        contents.append({"role": "user", "parts": [{"text": transaction_context}]})
        contents.append({"role": "model", "parts": [{"text": "Got it, I have your transaction data loaded and ready."}]})
    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": request.question}]})

    config = types.GenerateContentConfig(
        system_instruction=system_context,
        tools=[FINANCE_TOOLS],
    )

    async def generate():
        try:
            # Agentic loop: handle tool calls before streaming the final text response
            current_contents = list(contents)

            while True:
                # Collect a full non-streaming response to check for tool calls first
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=current_contents,
                    config=config,
                )

                candidate = response.candidates[0]
                parts = candidate.content.parts

                # Check if any part is a function call
                tool_call_parts = [p for p in parts if p.function_call is not None]

                if tool_call_parts:
                    # Append the model's tool-call turn to history
                    current_contents.append({
                        "role": "model",
                        "parts": [{"function_call": {"name": p.function_call.name, "args": dict(p.function_call.args)}} for p in tool_call_parts],
                    })

                    # Execute each tool and build function response parts
                    function_response_parts = []
                    for part in tool_call_parts:
                        fc = part.function_call
                        result = execute_tool(fc.name, dict(fc.args), request.transactions, request.stats)
                        function_response_parts.append({
                            "function_response": {
                                "name": fc.name,
                                "response": {"result": result},
                            }
                        })

                    current_contents.append({"role": "user", "parts": function_response_parts})
                    # Loop again so the model can generate its final text response
                    continue

                # No tool calls — yield the already-generated text parts
                text_parts = [p for p in parts if p.text]
                if text_parts:
                    for part in text_parts:
                        yield f"data: {json.dumps({'token': part.text})}\n\n"
                else:
                    yield f"data: {json.dumps({'token': ''})}\n\n"

                yield "data: [DONE]\n\n"
                break

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                yield f"data: {json.dumps({'error': 'The AI service has reached its daily request limit. Please try again tomorrow or upgrade your Gemini API plan.'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': f'Gemini error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })

