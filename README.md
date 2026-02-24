# Where Did My Money Go?

A personal finance analyzer powered by AI. Upload one or more bank or credit card transaction CSVs and get natural language spending insights, interactive visualizations, and a conversational chat interface to ask questions about your spending.

---

## Features

- **CSV upload** — supports multiple files; accepts any CSV with `date`, `description`, `amount`, and `category` columns
- **AI column mapping** — if your CSV uses different column names, Gemini automatically infers the correct mappings so you don't have to rename anything
- **On-demand AI spending narrative** — click "Generate Analysis" to get a friendly 3–4 paragraph Gemini-powered summary of your spending patterns with actionable suggestions
- **Category & merchant breakdowns** — ranked lists showing where your money is going
- **Interactive charts** — donut chart by category and a spending-over-time line chart with Daily / Weekly / Monthly / Quarterly / Yearly views (Recharts)
- **Spending trends** — compare any two periods side-by-side with per-category trend indicators
- **Streaming AI chat** — ask follow-up questions like *"How much did I spend on dining?"* or *"What was my biggest purchase?"* and watch the response stream in token by token
- **Function calling** — the chat assistant uses tool calls for precise filtering and aggregation over your transaction data rather than estimating from context

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, Tailwind CSS 4, Recharts |
| Backend | Python, FastAPI, pandas |
| AI | Google Gemini 2.5 Flash Lite (on-demand narrative, streaming chat, function calling) |

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # then add your GEMINI_API_KEY
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`. Auto-generated docs are at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Sample Data

Several sample CSVs are included in `sample_data/` so you can try the app without uploading real bank data:

| File | Description |
|------|-------------|
| `transactions_q1_2024.csv` | Q1 2024 transactions |
| `transactions_q2_2024.csv` | Q2 2024 transactions |
| `transactions_jan_feb_2024.csv` | January–February 2024 |
| `transactions_full_year_2024.csv` | Full year 2024 |

All sample files use the standard `date`, `description`, `amount`, `category` format. Try uploading multiple files at once to see multi-period trend analysis.

---

## Project Structure

```
where-did-my-money-go/
├── backend/
│   ├── main.py              # FastAPI app — analyze, on-demand narrative, streaming chat, function calling, column mapping
│   ├── requirements.txt
│   ├── .env.example
│   └── prompts/
│       ├── analyze_system.j2        # System prompt for spending narrative
│       ├── analyze_user.j2          # User prompt template for narrative
│       ├── chat_system.j2           # System prompt for chat assistant + tool descriptions
│       ├── chat_user.j2             # User prompt template with transaction context
│       └── column_mapping_user.j2   # Prompt for AI-powered CSV column inference
├── frontend/
│   └── src/
│       ├── App.jsx                  # Main layout, upload flow, dashboard
│       └── components/
│           ├── SpendingCharts.jsx   # Recharts visualizations
│           └── FloatingChat.jsx     # Streaming AI chat interface
└── sample_data/
    ├── transactions_q1_2024.csv
    ├── transactions_q2_2024.csv
    ├── transactions_jan_feb_2024.csv
    └── transactions_full_year_2024.csv
```

---

## License

MIT
