export interface ChatRequest {
  message: string;
  conversation_id: string | null;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
}

export async function sendMessage(
  message: string,
  conversationId: string | null
): Promise<ChatResponse> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL}/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(
      `Chat request failed: ${response.status}`
    );
  }

  return response.json();
}