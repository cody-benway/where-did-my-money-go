import { useState } from "react"
import SpendingCharts from "./components/SpendingCharts"
import ChatInterface from "./components/ChatInterface"

function App() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
    setResult(null)
    setError(null)
  }

  const handleClearFile = () => {
    setFile(null)
    setResult(null)
    setError(null)
  }

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append("file", file)

    try {
      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center p-8">
      <div className="w-full max-w-3xl">
        <h1 className="text-3xl font-bold text-gray-800 mb-2 text-center">
          Where Did My Money Go?
        </h1>
        <p className="text-gray-500 mb-8 text-center">
          Upload a transaction CSV to analyze your spending
        </p>

        <div className="bg-white rounded-2xl shadow p-8 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <label className="flex items-center justify-center flex-1 border-2 border-dashed border-indigo-300 rounded-lg p-4 cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition">
            <span className="text-indigo-600 font-medium">
              {file ? file.name : "Choose a CSV file..."}
            </span>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
            />
          </label>
          {file && (
            <button
              onClick={handleClearFile}
              title="Clear selected file"
              className="flex items-center justify-center w-10 h-10 rounded-full bg-red-100 hover:bg-red-200 text-red-600 transition flex-shrink-0"
            >
              ✕
            </button>
          )}
        </div>
          <button
            onClick={handleUpload}
            disabled={!file || loading}
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? "Analyzing..." : "Upload & Analyze"}
          </button>
          {error && <p className="mt-4 text-red-500 text-sm">{error}</p>}
        </div>

        {result && (
          <>
            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-white rounded-2xl shadow p-6">
                <p className="text-sm text-gray-500 mb-1">Total Income</p>
                <p className="text-2xl font-bold text-green-600">
                  ${result.stats.total_income.toFixed(2)}
                </p>
              </div>
              <div className="bg-white rounded-2xl shadow p-6">
                <p className="text-sm text-gray-500 mb-1">Total Spent</p>
                <p className="text-2xl font-bold text-red-500">
                  ${result.stats.total_spent.toFixed(2)}
                </p>
              </div>
            </div>

            {/* Spending by Category */}
            <div className="bg-white rounded-2xl shadow p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">
                Spending by Category
              </h2>
              {Object.entries(result.stats.by_category)
                .sort((a, b) => a[1] - b[1])
                .map(([category, amount]) => (
                  <div key={category} className="flex justify-between py-2 border-b last:border-0">
                    <span className="text-gray-600">{category}</span>
                    <span className="font-medium text-red-500">
                      ${Math.abs(amount).toFixed(2)}
                    </span>
                  </div>
                ))}
            </div>

            {/* Spending Charts */}
            <div className="mb-6">
              <SpendingCharts stats={result.stats} />
            </div>

            {/* Top Merchants */}
            <div className="bg-white rounded-2xl shadow p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">
                Top Merchants
              </h2>
              {Object.entries(result.stats.top_merchants)
                .sort((a, b) => a[1] - b[1])
                .map(([merchant, amount]) => (
                  <div key={merchant} className="flex justify-between py-2 border-b last:border-0">
                    <span className="text-gray-600">{merchant}</span>
                    <span className="font-medium text-red-500">
                      ${Math.abs(amount).toFixed(2)}
                    </span>
                  </div>
                ))}
            </div>

            {/* AI Narrative */}
            <div className="bg-white rounded-2xl shadow p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">
                AI Spending Analysis
              </h2>
              {result.narrative.split("\n\n").map((paragraph, i) => (
                <p key={i} className="text-gray-600 mb-3 leading-relaxed">
                  {paragraph}
                </p>
              ))}
            </div>

            {/* Chat Interface */}
            <div className="mb-6">
              <ChatInterface transactions={result.transactions} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default App