import { useState } from "react";
import { sendMessage } from "./api/chat";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] =
    useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSend = async () => {
    const currentMessage = message.trim();

    if (!currentMessage || loading) {
      return;
    }

    setMessages((previous) => [
      ...previous,
      { role: "user", content: currentMessage },
    ]);
    setMessage("");
    setLoading(true);
    setError("");

    try {
      const response = await sendMessage(
        currentMessage,
        conversationId
      );

      setConversationId(response.conversation_id);

      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: response.answer },
      ]);
    } catch {
      setError("Could not contact the assistant.");
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setConversationId(null);
    setMessage("");
    setError("");
  };

  return (
    <main>
      <h1>Insurance AI</h1>

      <button
        onClick={startNewConversation}
        disabled={loading}
      >
        New conversation
      </button>

      <section aria-live="polite">
        {messages.map((item, index) => (
          <div key={index}>
            <strong>
              {item.role === "user" ? "You" : "Assistant"}
            </strong>
            <p>{item.content}</p>
          </div>
        ))}

        {loading && <p>Thinking...</p>}
      </section>

      {error && <p>{error}</p>}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleSend();
        }}
      >
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask about your insurance..."
          disabled={loading}
        />

        <button type="submit" disabled={loading || !message.trim()}>
          Send
        </button>
      </form>
    </main>
  );
}

export default App;