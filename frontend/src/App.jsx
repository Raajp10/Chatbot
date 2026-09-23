import { useState } from "react";

import { postQuery } from "./api/query.js";
import DisclaimerBanner from "./components/DisclaimerBanner.jsx";

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const text = inputText.trim();
    if (!text || isSending) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInputText("");
    setIsSending(true);

    try {
      const response = await postQuery({ text, context: {} });
      setMessages((prev) => [...prev, { role: "assistant", response }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", response: { type: "error", message: error.message } },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="app">
      <DisclaimerBanner />
      <p>PNW Student Knowledge Chatbot</p>
      <ul className="message-list">
        {messages.map((message, index) => (
          <li key={index}>
            <strong>{message.role === "user" ? "You" : "Bot"}:</strong>{" "}
            {message.role === "user" ? message.text : JSON.stringify(message.response)}
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={inputText}
          onChange={(event) => setInputText(event.target.value)}
          placeholder="Ask a question about PNW..."
          disabled={isSending}
        />
        <button type="submit" disabled={isSending}>
          Send
        </button>
      </form>
    </div>
  );
}

export default App;
