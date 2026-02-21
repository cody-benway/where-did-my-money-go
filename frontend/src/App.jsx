import { useState, useEffect } from "react"
import SpendingCharts, { CATEGORY_COLORS } from "./components/SpendingCharts"
import FloatingChat from "./components/FloatingChat"

function TrendArrow({ direction, changePct }) {
  if (direction === "up") {
    return (
      <span className="flex items-center gap-1 text-red-500 font-medium text-sm">
        <span>↑</span>
        <span>{changePct.toFixed(1)}%</span>
      </span>
    )
  }
  if (direction === "down") {
    return (
      <span className="flex items-center gap-1 text-green-600 font-medium text-sm">
        <span>↓</span>
        <span>{changePct.toFixed(1)}%</span>
      </span>
    )
  }
  return <span className="text-gray-400 text-sm">—</span>
}

const TREND_PERIODS = ["Weekly", "Monthly", "Quarterly", "Yearly"]

function computeTrends(spending, fromPeriod, toPeriod) {
  if (!spending || !fromPeriod || !toPeriod || fromPeriod === toPeriod) return {}
  const fromData = spending[fromPeriod] ?? {}
  const toData = spending[toPeriod] ?? {}
  const allCategories = new Set([...Object.keys(fromData), ...Object.keys(toData)])
  const result = {}
  allCategories.forEach((category) => {
    const prev = fromData[category] ?? 0
    const curr = toData[category] ?? 0
    if (prev > 0) {
      const change_pct = ((curr - prev) / prev) * 100
      result[category] = {
        change_pct: Math.abs(change_pct).toFixed(1) * 1,
        direction: change_pct > 0 ? "up" : "down",
      }
    }
  })
  return result
}

function App() {
  const [files, setFiles] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [trendPeriod, setTrendPeriod] = useState("Monthly")
  const [trendFrom, setTrendFrom] = useState(null)
  const [trendTo, setTrendTo] = useState(null)

  // Reset From/To to the two most recent periods when granularity or result changes
  useEffect(() => {
    if (!result?.trends_by_period) return
    const allPeriods = result.trends_by_period[trendPeriod]?.all_periods ?? []
    if (allPeriods.length >= 2) {
      setTrendFrom(allPeriods[allPeriods.length - 2])
      setTrendTo(allPeriods[allPeriods.length - 1])
    } else if (allPeriods.length === 1) {
      setTrendFrom(allPeriods[0])
      setTrendTo(allPeriods[0])
    } else {
      setTrendFrom(null)
      setTrendTo(null)
    }
  }, [trendPeriod, result])

  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files)
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name))
      const newFiles = selected.filter((f) => !existingNames.has(f.name))
      return [...prev, ...newFiles]
    })
    setResult(null)
    setError(null)
    // Reset input so the same file can be re-added after removal
    e.target.value = ""
  }

  const handleRemoveFile = (name) => {
    setFiles((prev) => prev.filter((f) => f.name !== name))
    setResult(null)
    setError(null)
  }

  const handleClearFiles = () => {
    setFiles([])
    setResult(null)
    setError(null)
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    setLoading(true)
    setError(null)

    const formData = new FormData()
    files.forEach((f) => formData.append("files", f))

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/analyze`, {
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

  const categoryEntries = result
    ? Object.entries(result.stats.by_category).sort((a, b) => b[1] - a[1])
    : []

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 flex flex-col items-center p-8">
      <div className="w-full max-w-3xl">
        <h1 className="text-3xl font-bold text-gray-800 mb-2 text-center">
          Where Did My Money Go?
        </h1>
        <p className="text-gray-500 mb-8 text-center">
          Upload one or more transaction CSVs to analyze your spending
        </p>

        <div className="bg-white rounded-2xl shadow p-8 mb-6">
          {/* Drop zone / file picker */}
          <label className="flex items-center justify-center w-full border-2 border-dashed border-indigo-300 rounded-lg p-4 cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition mb-3">
            <span className="text-indigo-600 font-medium">
              + Choose CSV files...
            </span>
            <input
              type="file"
              accept=".csv"
              multiple
              onChange={handleFileChange}
              className="hidden"
            />
          </label>

          {/* Selected file list */}
          {files.length > 0 && (
            <div className="mb-4 space-y-2">
              {files.map((f) => (
                <div key={f.name} className="flex items-center justify-between bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2">
                  <span className="text-sm text-indigo-700 truncate flex-1 mr-2">{f.name}</span>
                  <button
                    onClick={() => handleRemoveFile(f.name)}
                    title="Remove file"
                    className="flex-shrink-0 text-indigo-400 hover:text-red-500 transition text-sm font-medium"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                onClick={handleClearFiles}
                className="text-xs text-gray-400 hover:text-red-500 transition mt-1"
              >
                Remove all
              </button>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={files.length === 0 || loading}
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? "Analyzing..." : `Upload & Analyze${files.length > 1 ? ` (${files.length} files)` : ""}`}
          </button>
          {error && <p className="mt-4 text-red-500 text-sm">{error}</p>}
        </div>

        {loading && (
          <div className="flex flex-col items-center gap-3 py-12 text-gray-500">
            <svg
              className="animate-spin h-8 w-8 text-indigo-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-sm">Analyzing your transactions...</p>
          </div>
        )}

        {result && (
          <>
            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-white rounded-2xl shadow p-6 border-l-4 border-green-400">
                <p className="text-sm text-gray-500 mb-1">Total Income</p>
                <p className="text-2xl font-bold text-green-600">
                  ${result.stats.total_income.toFixed(2)}
                </p>
              </div>
              <div className="bg-white rounded-2xl shadow p-6 border-l-4 border-red-400">
                <p className="text-sm text-gray-500 mb-1">Total Spent</p>
                <p className="text-2xl font-bold text-red-500">
                  ${result.stats.total_spent.toFixed(2)}
                </p>
              </div>
            </div>

            {/* Spending Charts (donut + time toggle) */}
            <div className="mb-6">
              <SpendingCharts stats={result.stats} />
            </div>

            {/* Spending Trends */}
            {result.trends_by_period && (
              <div className="bg-white rounded-2xl shadow p-6 mb-6">
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <h2 className="text-lg font-semibold text-gray-700">Spending Trends</h2>
                  <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                    {TREND_PERIODS.map((period) => (
                      <button
                        key={period}
                        onClick={() => setTrendPeriod(period)}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                          trendPeriod === period
                            ? "bg-indigo-600 text-white shadow-sm"
                            : "text-gray-500 hover:text-gray-700"
                        }`}
                      >
                        {period}
                      </button>
                    ))}
                  </div>
                </div>

                {(() => {
                  const periodData = result.trends_by_period[trendPeriod]
                  const allPeriods = periodData?.all_periods ?? []
                  const spending = periodData?.spending ?? {}
                  const sameSelection = trendFrom === trendTo
                  const trends = (!sameSelection && trendFrom && trendTo)
                    ? computeTrends(spending, trendFrom, trendTo)
                    : {}
                  const hasAnyTrend = Object.keys(trends).length > 0

                  return (
                    <>
                      {/* From / To dropdowns */}
                      {allPeriods.length >= 2 ? (
                        <div className="flex items-center gap-2 mb-3 flex-wrap">
                          <span className="text-xs text-gray-500 font-medium">Compare</span>
                          <select
                            value={trendFrom ?? ""}
                            onChange={(e) => setTrendFrom(e.target.value)}
                            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white text-gray-700"
                          >
                            {allPeriods.map((p) => (
                              <option key={p} value={p}>{p}</option>
                            ))}
                          </select>
                          <span className="text-xs text-gray-500 font-medium">to</span>
                          <select
                            value={trendTo ?? ""}
                            onChange={(e) => setTrendTo(e.target.value)}
                            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white text-gray-700"
                          >
                            {allPeriods.map((p) => (
                              <option key={p} value={p}>{p}</option>
                            ))}
                          </select>
                        </div>
                      ) : null}

                      {sameSelection && trendFrom ? (
                        <p className="text-xs text-amber-600 mb-3">Select two different periods to compare.</p>
                      ) : !trendFrom || !trendTo ? (
                        <p className="text-xs text-gray-400 mb-3">Not enough data to compare periods.</p>
                      ) : null}

                      {hasAnyTrend ? (
                        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                          {categoryEntries.map(([category], index) => {
                            const trend = trends[category]
                            return (
                              <div key={category} className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2 min-w-0">
                                  <span
                                    className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                                    style={{ backgroundColor: CATEGORY_COLORS[index % CATEGORY_COLORS.length] }}
                                  />
                                  <span className="text-sm text-gray-600 truncate">{category}</span>
                                </div>
                                {trend ? (
                                  <TrendArrow direction={trend.direction} changePct={trend.change_pct} />
                                ) : (
                                  <span className="text-xs text-gray-400">No data</span>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      ) : (!sameSelection && trendFrom && trendTo) ? (
                        <p className="text-xs text-gray-400">Not enough data to compare these periods.</p>
                      ) : null}
                    </>
                  )
                })()}
              </div>
            )}

            {/* Top Merchants */}
            <div className="bg-white rounded-2xl shadow p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">Top Merchants</h2>
              {Object.entries(result.stats.top_merchants)
                .sort((a, b) => b[1] - a[1])
                .map(([merchant, amount], index) => (
                  <div
                    key={merchant}
                    className={`flex justify-between py-2 border-b last:border-0 px-2 rounded ${
                      index % 2 === 0 ? "bg-gray-50" : ""
                    }`}
                  >
                    <span className="text-gray-600">{merchant}</span>
                    <span className="font-medium text-red-500">${amount.toFixed(2)}</span>
                  </div>
                ))}
            </div>

            {/* AI Narrative */}
            {result.narrative && (
              <div className="bg-white rounded-2xl shadow p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-700 mb-2">AI Spending Analysis</h2>
                <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
                  <span className="text-amber-500 flex-shrink-0">⚠</span>
                  <p className="text-xs text-amber-700">
                    AI-generated analysis. Results may be inaccurate — always verify with your actual statements.
                  </p>
                </div>
                {result.narrative.split("\n\n").map((paragraph, i) => (
                  <p key={i} className="text-gray-600 mb-3 leading-relaxed">
                    {paragraph}
                  </p>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      <FloatingChat transactions={result?.transactions} />
    </div>
  )
}

export default App
