import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    Cell,
  } from "recharts"

export default function SpendingCharts({ stats, rawTransactions }) {
  const categoryData = Object.entries(stats.by_category)
    .map(([category, amount]) => ({
      category,
      amount: Math.abs(amount),
    }))
    .sort((a, b) => a.amount - b.amount)

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">
          Spending by Category
        </h2>
        <ResponsiveContainer width="100%" height={categoryData.length * 40 + 20}>
          <BarChart
            data={categoryData}
            layout="vertical"
            margin={{ top: 0, right: 60, left: 10, bottom: 0 }}
          >
            <XAxis
              type="number"
              tickFormatter={(v) => `$${v}`}
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="category"
              tick={{ fontSize: 13 }}
              width={110}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip formatter={(value) => `$${value.toFixed(2)}`} />
            <Bar dataKey="amount" fill="#6366f1" radius={[0, 4, 4, 0]}>
              {categoryData.map((_, index) => (
                <Cell key={index} fill="#6366f1" fillOpacity={0.7 + (index / categoryData.length) * 0.3} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}