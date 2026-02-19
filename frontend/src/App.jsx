import { useState } from "react"

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

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append("file", file)

    try {
      const res = await fetch("http://localhost:8000/upload", {
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
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
      <h1 className="text-3xl font-bold text-gray-800 mb-2">
        Where Did My Money Go?
      </h1>
      <p className="text-gray-500 mb-8">
        Upload a transaction CSV to analyze your spending
      </p>

      <div className="bg-white rounded-2xl shadow p-8 w-full max-w-lg">
        <input
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          className="block w-full text-sm text-gray-500 mb-4"
        />
        <button
          onClick={handleUpload}
          disabled={!file || loading}
          className="w-full bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          {loading ? "Analyzing..." : "Upload & Analyze"}
        </button>

        {error && (
          <p className="mt-4 text-red-500 text-sm">{error}</p>
        )}

        {result && (
          <div className="mt-6">
            <p className="text-gray-700 font-medium">
              ✅ {result.rows} transactions loaded
            </p>
            <p className="text-gray-500 text-sm mt-1">
              Columns: {result.columns.join(", ")}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App