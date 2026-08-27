export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  answer: string;
}

export async function sendMessage(
  message: string
): Promise<ChatResponse> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL}/api/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
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