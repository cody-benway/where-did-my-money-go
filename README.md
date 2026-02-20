# Where Did My Money Go?

A personal finance analyzer powered by AI. Upload a bank or credit card transaction CSV and get natural language spending insights, interactive visualizations, and a conversational chat interface to ask questions about your spending.

**Live demo:** *(coming soon)*

---

## Features

- **CSV upload** — supports any bank or credit card export with `date`, `description`, `amount`, and `category` columns
- **AI spending narrative** — Gemini generates a friendly 3–4 paragraph analysis of your spending patterns with actionable suggestions
- **Category & merchant breakdowns** — ranked lists showing where money is going
- **Interactive charts** — horizontal bar chart by category and a daily spending line chart (Recharts)
- **Conversational chat** — ask follow-up questions like *"How much did I spend on dining?"* or *"What was my biggest purchase?"*

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, Tailwind CSS, Recharts |
| Backend | Python, FastAPI, pandas |
| AI | Google Gemini 3 Flash |

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

The API will be available at `http://localhost:8000`. You can explore the auto-generated docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Sample Data

A sample CSV is included at `sample_data/sample_transactions.csv` so you can try the app without uploading real bank data.

---

## Project Structure

```
where-did-my-money-go/
├── backend/
│   ├── main.py              # FastAPI app — upload, analyze, and chat endpoints
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── App.jsx              # Main layout and upload flow
│       └── components/
│           ├── SpendingCharts.jsx   # Recharts visualizations
│           └── ChatInterface.jsx    # AI chat component
└── sample_data/
    └── sample_transactions.csv
```

---

## License

MIT
