import { useState } from "react"
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts"

const CATEGORY_COLORS = [
  "#6366f1", // indigo
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#f59e0b", // amber
  "#14b8a6", // teal
  "#f43f5e", // rose
  "#0ea5e9", // sky
  "#10b981", // emerald
  "#f97316", // orange
  "#a855f7", // purple
]

const TIME_PERIODS = ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"]

function aggregateSpending(dailySpending, period) {
  if (!dailySpending || dailySpending.length === 0) return []

  if (period === "Daily") return dailySpending

  const buckets = {}
  dailySpending.forEach(({ date, amount }) => {
    const [month, day, year] = date.split("/").map(Number)
    const d = new Date(year, month - 1, day)
    let key

    if (period === "Weekly") {
      const startOfYear = new Date(year, 0, 1)
      const weekNum = Math.ceil(((d - startOfYear) / 86400000 + startOfYear.getDay() + 1) / 7)
      key = `${year} Wk ${weekNum}`
    } else if (period === "Monthly") {
      key = d.toLocaleString("default", { month: "short", year: "numeric" })
    } else if (period === "Quarterly") {
      const q = Math.ceil(month / 3)
      key = `Q${q} ${year}`
    } else if (period === "Yearly") {
      key = `${year}`
    }

    buckets[key] = (buckets[key] || 0) + amount
  })

  return Object.entries(buckets).map(([date, amount]) => ({ date, amount: parseFloat(amount.toFixed(2)) }))
}


export default function SpendingCharts({ stats }) {
  const [timePeriod, setTimePeriod] = useState("Daily")

  const categoryData = Object.entries(stats.by_category)
    .map(([category, amount]) => ({ name: category, value: amount }))
    .sort((a, b) => b.value - a.value)

  const timeData = aggregateSpending(stats.daily_spending, timePeriod)

  return (
    <div className="space-y-6">

      {/* Spending by Category Donut Chart */}
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">Spending by Category</h2>
        <div className="flex flex-col items-center">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={categoryData}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={110}
                paddingAngle={3}
                dataKey="value"
              >
                {categoryData.map((_, index) => (
                  <Cell key={index} fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value, name) => [`$${value.toFixed(2)}`, name]} />
            </PieChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="w-full grid grid-cols-2 gap-x-6 gap-y-2 mt-2">
            {categoryData.map((entry, index) => (
              <div key={entry.name} className="flex items-center gap-2">
                <span
                  className="inline-block w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: CATEGORY_COLORS[index % CATEGORY_COLORS.length] }}
                />
                <span className="text-sm text-gray-600 truncate flex-1">{entry.name}</span>
                <span className="text-sm font-medium text-gray-800">${entry.value.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Spending Over Time Line Chart */}
      <div className="bg-white rounded-2xl shadow p-6">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-gray-700">Spending Over Time</h2>
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {TIME_PERIODS.map((period) => (
              <button
                key={period}
                onClick={() => setTimePeriod(period)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                  timePeriod === period
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {period}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={timeData} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value) => `$${value.toFixed(2)}`} />
            <Line
              type="monotone"
              dataKey="amount"
              stroke="#6366f1"
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

    </div>
  )
}

export { CATEGORY_COLORS }
