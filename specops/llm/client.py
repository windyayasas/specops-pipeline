"""Groq LLM client wrapper with retry logic."""

import hashlib
import time
from typing import Any

import structlog
from groq import Groq, RateLimitError

logger = structlog.get_logger(__name__)


class GroqClient:
    """Wrapper around Groq API client with retry and audit logging."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        max_retries: int = 3,
    ):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key
            model: Model name (default: llama-3.3-70b-versatile)
            max_retries: Maximum number of retries on rate limit
        """
        self.client = Groq(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def hash_prompt(self, prompt: str) -> str:
        """
        Hash a prompt for audit logging (deterministic, no PII).

        Args:
            prompt: The prompt text

        Returns:
            SHA256 hash (first 16 chars)
        """
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return digest[:16]

    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """
        Call Groq API with automatic retry on rate limit.

        Args:
            prompt: User prompt
            system_prompt: System context (optional)
            temperature: Sampling temperature
            max_tokens: Max response tokens
            json_mode: If True, expect JSON response

        Returns:
            Model response text

        Raises:
            RuntimeError: If all retries fail
        """
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        prompt_hash = self.hash_prompt(prompt)
        logger.debug(
            "groq_call_starting",
            model=self.model,
            prompt_hash=prompt_hash,
            json_mode=json_mode,
        )

        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                result = response.choices[0].message.content
                if result is None:
                    raise RuntimeError("Empty response from Groq")

                logger.info(
                    "groq_call_success",
                    model=self.model,
                    prompt_hash=prompt_hash,
                    response_length=len(result),
                    attempt=attempt + 1,
                )

                return result

            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.warning(
                        "groq_rate_limit_retry",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        wait_seconds=wait_time,
                        prompt_hash=prompt_hash,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "groq_rate_limit_exhausted",
                        attempts=self.max_retries,
                        prompt_hash=prompt_hash,
                    )

        # All retries failed
        raise RuntimeError(
            f"Groq API failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    def json_call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Call Groq API expecting JSON response and parse it.

        Args:
            prompt: User prompt
            system_prompt: System context
            temperature: Sampling temperature
            max_tokens: Max response tokens

        Returns:
            Parsed JSON response as dict

        Raises:
            ValueError: If response is not valid JSON
            RuntimeError: If API call fails
        """
        import json

        response_text = self.call(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        try:
            # Strip markdown code blocks if present (```json ... ```)
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                # Remove opening ``` or ```json
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:].lstrip()
                else:
                    cleaned = cleaned[3:].lstrip()
                # Remove closing ```
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].rstrip()
            
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "groq_json_parse_error",
                response=response_text[:200],
                error=str(e),
            )
            raise ValueError(f"Failed to parse JSON response from Groq: {e}") from e
