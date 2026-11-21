
import asyncio
import logging
import time
from typing import Any, TypeVar
import httpx
from google.genai._interactions import APIConnectionError, APITimeoutError
from google.genai import types as genai_types

from google import genai
from pydantic import BaseModel

from app.llm.base import BaseLLMProvider
from app.llm.diagnostics import log_failure, status_code

logger = logging.getLogger(__name__)


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
        request_timeout: float = 20.0,
        call_timeout: float = 20.0,
        max_attempts: int = 1,
    ):
        if request_timeout <= 0 or call_timeout <= 0 or max_attempts not in (1, 2):
            raise ValueError("Provider deadlines must be positive; at most one retry is allowed.")
        self.request_timeout = request_timeout
        self.call_timeout = call_timeout
        self.max_attempts = max_attempts
        self._client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=int(request_timeout * 1000),
                retry_options=genai_types.HttpRetryOptions(
                    attempts=0,
                ),
            ),
        )

        self._async_client = self._client.aio
        self.model = model

    async def _create(self, *, stage, **kwargs):
        deadline = time.monotonic() + self.call_timeout
        last_logged = None
        attempt = 0
        try:
            async with asyncio.timeout(self.call_timeout):
                for attempt in range(1, self.max_attempts + 1):
                    timeout = min(self.request_timeout, deadline - time.monotonic())
                    try:
                        # A single attempt by default; optional fast-error retries
                        # share the same call budget and never repeat a timed-out call.
                        return await asyncio.wait_for(
                            self._async_client.interactions.create(**kwargs, timeout=timeout),
                            timeout=timeout,
                        )
                    except Exception as exc:
                        log_failure(logger, stage, exc, attempt)
                        last_logged = exc
                        timeout_failure = isinstance(exc, (TimeoutError, httpx.TimeoutException, APITimeoutError))
                        transient = (status_code(exc) in {408, 429, 500, 502, 503, 504}
                                     or isinstance(exc, (httpx.TransportError, APIConnectionError)))
                        if timeout_failure or not transient or attempt == self.max_attempts:
                            raise
                        await asyncio.sleep(min(0.5, max(0, deadline - time.monotonic())))
        except TimeoutError as exc:
            if exc is not last_logged:
                log_failure(logger, stage, exc, attempt)
            raise

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

        response = await self._create(
            stage="answer_generation",
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

        response = await self._create(
            stage=f"structured:{response_model.__name__}",
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
