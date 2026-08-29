import os

from app.ai.client import client
from app.ai.prompts import SYSTEM_PROMPT


async def generate_answer(message: str) -> str:
    response = await client.chat.completions.create(
        model=os.getenv("GROQ_MODEL"),
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": message,
            },
        ],
    )

    return response.choices[0].message.content or ""