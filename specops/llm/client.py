"""Groq LLM client wrapper with retry logic and response caching."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, cast

import structlog
from groq import Groq, RateLimitError

logger = structlog.get_logger(__name__)


class LLMCache:
    """Simple file-based cache for LLM responses."""

    def __init__(self, cache_dir: Path = Path("outputs/.llm_cache")):
        """Initialize cache directory."""
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate cache key from prompt and system prompt."""
        combined = f"{system_prompt or ''}:::{prompt}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Any | None:
        """Retrieve cached response if exists."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("llm_cache_hit", cache_key=cache_key[:8])
                return data.get("response")
            except Exception as e:
                logger.warning("llm_cache_read_error", error=str(e))
                return None
        return None

    def set(self, cache_key: str, response: str) -> None:
        """Store response in cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"response": response}, f)
            logger.info("llm_cache_saved", cache_key=cache_key[:8])
        except Exception as e:
            logger.warning("llm_cache_write_error", error=str(e))


class GroqClient:
    """Wrapper around Groq API client with retry logic and caching."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        max_retries: int = 3,
        enable_cache: bool = True,
    ):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key
            model: Model name (default: llama-3.3-70b-versatile)
            max_retries: Maximum number of retries on rate limit
            enable_cache: Enable response caching to reduce API calls
        """
        self.client = Groq(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.cache = LLMCache() if enable_cache else None

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
        Call Groq API with automatic retry on rate limit and response caching.

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
        prompt_hash = self.hash_prompt(prompt)

        # Check cache first
        if self.cache:
            cache_key = self.cache.get_cache_key(prompt, system_prompt)
            cached_response = self.cache.get(cache_key)
            if cached_response:
                logger.debug(
                    "groq_call_cached",
                    model=self.model,
                    prompt_hash=prompt_hash,
                )
                return cast(str, cached_response)

        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

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
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                result = cast(str, response.choices[0].message.content)
                if not result:
                    raise RuntimeError("Empty response from Groq")

                logger.info(
                    "groq_call_success",
                    model=self.model,
                    prompt_hash=prompt_hash,
                    response_length=len(result),
                    attempt=attempt + 1,
                )

                # Cache the response
                if self.cache:
                    cache_key = self.cache.get_cache_key(prompt, system_prompt)
                    self.cache.set(cache_key, result)

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

            return json.loads(cleaned)  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            logger.error(
                "groq_json_parse_error",
                response=response_text[:200],
                error=str(e),
            )
            raise ValueError(f"Failed to parse JSON response from Groq: {e}") from e
