
from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel

from app.llm.base import BaseLLMProvider


T = TypeVar(
    "T",
    bound=BaseModel,
)


# JSON Schema keywords supported by Gemini structured outputs.
_GEMINI_SCHEMA_KEYS = {
    "$id",
    "$defs",
    "$ref",
    "$anchor",
    "type",
    "format",
    "title",
    "description",
    "enum",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "anyOf",
    "oneOf",
    "properties",
    "additionalProperties",
    "required",
    "propertyOrdering",
}

_GEMINI_SUPPORTED_FORMATS = {
    "date",
    "date-time",
    "time",
}


def _sanitize_gemini_schema(node: Any) -> Any:
    """
    Remove JSON Schema keywords that Gemini structured
    outputs do not document as supported.

    Pydantic remains responsible for full validation
    after Gemini returns its response.
    """

    if isinstance(node, list):
        return [
            _sanitize_gemini_schema(item)
            for item in node
        ]

    if not isinstance(node, dict):
        return node

    sanitized = {}

    for key, value in node.items():

        # Preserve property names and definition names.
        if key in {"properties", "$defs"}:
            sanitized[key] = {
                name: _sanitize_gemini_schema(schema)
                for name, schema in value.items()
            }

        elif key in {"items", "additionalProperties"}:
            sanitized[key] = _sanitize_gemini_schema(value)

        elif key in {"anyOf", "oneOf", "prefixItems"}:
            sanitized[key] = [
                _sanitize_gemini_schema(schema)
                for schema in value
            ]

        elif key in _GEMINI_SCHEMA_KEYS:

            # UUID strings are validated by Pydantic after parsing.
            if (
                key == "format"
                and value not in _GEMINI_SUPPORTED_FORMATS
            ):
                continue

            sanitized[key] = value

        # Unsupported keys such as minLength, maxLength,
        # default and pattern are intentionally omitted.

    return sanitized


class GeminiProvider(BaseLLMProvider):

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
    ):
        self._client = genai.Client(
            api_key=api_key,
        )

        self._async_client = self._client.aio
        self.model = model

    @staticmethod
    def _build_input(
        *,
        user_message: str,
        context: str | None,
    ) -> str:

        if not context:
            return user_message

        return f"""
Context:
{context}

User question:
{user_message}
"""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str | None = None,
    ) -> str:

        response = await self._async_client.interactions.create(
            model=self.model,
            system_instruction=system_prompt,
            input=self._build_input(
                user_message=user_message,
                context=context,
            ),
            store=False,
        )

        content = response.output_text

        if not content:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return content

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        context: str | None = None,
        strict: bool = False,
    ) -> T:

        # Gemini has no separate Groq-style strict flag.
        # The JSON schema is sent to Gemini, and Pydantic
        # performs the complete validation afterwards.

        schema = _sanitize_gemini_schema(
            response_model.model_json_schema()
        )

        response = await self._async_client.interactions.create(
            model=self.model,
            system_instruction=system_prompt,
            input=self._build_input(
                user_message=user_message,
                context=context,
            ),
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
            store=False,
        )

        content = response.output_text

        if not content:
            raise RuntimeError(
                "Gemini returned an empty structured response."
            )

        return response_model.model_validate_json(content)
