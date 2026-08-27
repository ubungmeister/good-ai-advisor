import { useState } from "react";
import { sendMessage } from "./api/chat";


function App() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSend = async () => {
    if (!message.trim()) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await sendMessage(message);
      setAnswer(response.answer);
    } catch {
      setError("Could not contact the assistant.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main>
      <h1>Insurance AI</h1>

      <input
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Ask about your insurance..."
      />

      <button
        onClick={handleSend}
        disabled={loading}
      >
        {loading ? "Thinking..." : "Send"}
      </button>

      {error && <p>{error}</p>}

      {answer && (
        <section>
          <strong>Assistant</strong>
          <p>{answer}</p>
        </section>
      )}
    </main>
  );
}


export default App;