"""Tests for LLM client and response cache."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specops.llm.client import GroqClient, LLMCache


# ---------------------------------------------------------------------------
# LLMCache
# ---------------------------------------------------------------------------


class TestLLMCache:
    def test_cache_miss_returns_none(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        result = cache.get("nonexistent_key_abc")
        assert result is None

    def test_cache_set_and_get(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        key = cache.get_cache_key("hello world")
        cache.set(key, "the cached response")
        result = cache.get(key)
        assert result == "the cached response"

    def test_cache_key_deterministic(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        key1 = cache.get_cache_key("same prompt")
        key2 = cache.get_cache_key("same prompt")
        assert key1 == key2

    def test_cache_key_different_prompts(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        key1 = cache.get_cache_key("prompt A")
        key2 = cache.get_cache_key("prompt B")
        assert key1 != key2

    def test_cache_key_includes_system_prompt(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        key1 = cache.get_cache_key("prompt", system_prompt=None)
        key2 = cache.get_cache_key("prompt", system_prompt="you are an assistant")
        assert key1 != key2

    def test_cache_dir_created_on_init(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "nested" / "deep" / "cache"
        LLMCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_cache_handles_corrupt_file_gracefully(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        key = cache.get_cache_key("test prompt")
        # Write invalid JSON to the cache file
        cache_file = cache.cache_dir / f"{key}.json"
        cache_file.write_text("not-valid-json!!!")
        result = cache.get(key)
        assert result is None

    def test_cache_overwrites_existing_key(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=tmp_path / "cache")
        key = cache.get_cache_key("my prompt")
        cache.set(key, "first response")
        cache.set(key, "second response")
        assert cache.get(key) == "second response"


# ---------------------------------------------------------------------------
# GroqClient
# ---------------------------------------------------------------------------


class TestGroqClient:
    def test_hash_prompt_is_deterministic(self) -> None:
        with patch("specops.llm.client.Groq"):
            c = GroqClient(api_key="test-key", enable_cache=False)
        assert c.hash_prompt("hello") == c.hash_prompt("hello")

    def test_hash_prompt_returns_16_chars(self) -> None:
        with patch("specops.llm.client.Groq"):
            c = GroqClient(api_key="test-key", enable_cache=False)
        assert len(c.hash_prompt("some text")) == 16

    def test_hash_prompt_different_inputs_differ(self) -> None:
        with patch("specops.llm.client.Groq"):
            c = GroqClient(api_key="test-key", enable_cache=False)
        assert c.hash_prompt("abc") != c.hash_prompt("xyz")

    def test_call_returns_response_text(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "Hello from LLM!"
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False)
            result = c.call("say hello")

        assert result == "Hello from LLM!"

    def test_call_uses_cached_response(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_cache = MagicMock()
            mock_cache.get_cache_key.return_value = "cached_key"
            mock_cache.get.return_value = "from cache"

            c = GroqClient(api_key="test-key", enable_cache=True)
            c.cache = mock_cache
            result = c.call("test prompt")

        assert result == "from cache"
        MockGroq.return_value.chat.completions.create.assert_not_called()

    def test_call_stores_response_in_cache(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "fresh response"
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            mock_cache = MagicMock()
            mock_cache.get_cache_key.return_value = "some_key"
            mock_cache.get.return_value = None  # Cache miss

            c = GroqClient(api_key="test-key", enable_cache=True)
            c.cache = mock_cache
            result = c.call("test prompt")

        assert result == "fresh response"
        mock_cache.set.assert_called_once_with("some_key", "fresh response")

    def test_call_with_system_prompt_includes_both_messages(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "answer"
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False)
            c.call("user question", system_prompt="you are an expert")

        call_kwargs = MockGroq.return_value.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "you are an expert"
        assert messages[1]["role"] == "user"

    def test_call_retries_on_rate_limit_then_succeeds(self) -> None:
        import httpx
        from groq import RateLimitError

        with patch("specops.llm.client.Groq") as MockGroq, patch("specops.llm.client.time.sleep"):
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "ok after retry"

            fake_http_resp = MagicMock(spec=httpx.Response)
            fake_http_resp.status_code = 429

            MockGroq.return_value.chat.completions.create.side_effect = [
                RateLimitError("rate limited", response=fake_http_resp, body=None),
                mock_resp,
            ]

            c = GroqClient(api_key="test-key", enable_cache=False, max_retries=3)
            result = c.call("prompt")

        assert result == "ok after retry"

    def test_call_raises_after_all_retries_exhausted(self) -> None:
        import httpx
        from groq import RateLimitError

        with patch("specops.llm.client.Groq") as MockGroq, patch("specops.llm.client.time.sleep"):
            fake_http_resp = MagicMock(spec=httpx.Response)
            fake_http_resp.status_code = 429

            MockGroq.return_value.chat.completions.create.side_effect = RateLimitError(
                "rate limited", response=fake_http_resp, body=None
            )

            c = GroqClient(api_key="test-key", enable_cache=False, max_retries=2)
            with pytest.raises(RuntimeError, match="Groq API failed"):
                c.call("prompt")

    def test_call_raises_on_empty_response(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = None
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False, max_retries=1)
            with pytest.raises(RuntimeError):
                c.call("prompt")

    def test_json_call_parses_valid_json(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = '{"key": "value", "count": 42}'
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False)
            result = c.json_call("return json")

        assert result == {"key": "value", "count": 42}

    def test_json_call_strips_markdown_code_block(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "```json\n{\"x\": 1}\n```"
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False)
            result = c.json_call("return json")

        assert result == {"x": 1}

    def test_json_call_strips_plain_code_block(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "```\n{\"x\": 2}\n```"
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False)
            result = c.json_call("return json")

        assert result == {"x": 2}

    def test_json_call_raises_on_invalid_json(self) -> None:
        with patch("specops.llm.client.Groq") as MockGroq:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "this is not json at all"
            MockGroq.return_value.chat.completions.create.return_value = mock_resp

            c = GroqClient(api_key="test-key", enable_cache=False)
            with pytest.raises(ValueError, match="Failed to parse JSON"):
                c.json_call("return json")

    def test_cache_disabled_when_enable_cache_false(self) -> None:
        with patch("specops.llm.client.Groq"):
            c = GroqClient(api_key="test-key", enable_cache=False)
        assert c.cache is None

    def test_cache_enabled_by_default(self) -> None:
        with patch("specops.llm.client.Groq"):
            c = GroqClient(api_key="test-key")
        assert c.cache is not None
