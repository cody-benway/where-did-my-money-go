import { useState, useEffect, useRef } from "react"
import ReactMarkdown from "react-markdown"

const API_URL = import.meta.env.VITE_API_URL

export default function FloatingChat({ transactions, stats }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! Ask me anything about your spending. For example: \"How much did I spend on dining?\" or \"What was my biggest purchase?\"" }
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading, isOpen])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = { role: "user", content: input }
    const historyForRequest = messages.filter((_, i) => i > 0)
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput("")
    setLoading(true)

    // Add an empty assistant message that we'll stream into
    const assistantPlaceholder = { role: "assistant", content: "" }
    setMessages([...updatedMessages, assistantPlaceholder])

    try {
      const res = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: input,
          transactions: transactions ?? [],
          stats: stats ?? {},
          history: historyForRequest,
        }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || "Request failed")
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      let accumulated = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const payload = line.slice(6).trim()
          if (payload === "[DONE]") break

          try {
            const parsed = JSON.parse(payload)
            if (parsed.error) {
              throw new Error(parsed.error)
            }
            if (parsed.token) {
              accumulated += parsed.token
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = { role: "assistant", content: accumulated }
                return updated
              })
            }
          } catch (parseErr) {
            if (parseErr.message !== "Unexpected end of JSON input") {
              throw parseErr
            }
          }
        }
      }

      // If nothing was streamed, show a fallback
      if (!accumulated) {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: "assistant", content: "Sorry, I didn't get a response. Please try again." }
          return updated
        })
      }
    } catch (err) {
      const isNetworkError = err instanceof TypeError && err.message === "Failed to fetch"
      const errorMessage = isNetworkError
        ? "I'm having trouble connecting to the server. Make sure the backend is running and try again."
        : err.message || "Sorry, something went wrong. Please try again."
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: "assistant", content: errorMessage }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">

      {/* Chat Panel */}
      {isOpen && (
        <div className="mb-4 w-80 bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden border border-gray-100">
          {/* Header */}
          <div className="bg-indigo-600 px-4 py-3 flex items-center justify-between">
            <span className="text-white font-medium text-sm">Ask About Your Spending</span>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white/70 hover:text-white text-lg leading-none"
            >
              ✕
            </button>
          </div>

          {/* Disclaimer */}
          <div className="flex items-start gap-2 bg-amber-50 border-b border-amber-100 px-4 py-2">
            <span className="text-amber-500 text-xs mt-0.5 flex-shrink-0">⚠</span>
            <p className="text-xs text-amber-700">AI can make mistakes. Double-check important financial decisions.</p>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-80">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`rounded-2xl px-4 py-2 max-w-xs text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-700"
                  }`}
                >
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      ul: ({ children }) => <ul className="list-disc list-inside mb-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal list-inside mb-1">{children}</ol>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                  {/* Blinking cursor while this message is being streamed */}
                  {loading && i === messages.length - 1 && msg.role === "assistant" && (
                    <span className="inline-block w-0.5 h-3.5 bg-gray-500 ml-0.5 align-middle animate-pulse" />
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-100 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question..."
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="bg-indigo-600 text-white px-3 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm"
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-indigo-600 hover:bg-indigo-700 text-white w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition text-2xl"
      >
        {isOpen ? "✕" : "💬"}
      </button>
    </div>
  )
}
