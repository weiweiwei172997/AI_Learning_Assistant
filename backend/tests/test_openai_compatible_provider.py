from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from backend.providers.base import ModelProviderError, TextGenerationRequest
from backend.providers.openai_compatible import OpenAICompatibleTextProvider


class FakeStream:
    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error
        self.closed = False

    def __iter__(self):
        yield from self.chunks
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


def chunk(content=None, **delta):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content, **delta))])


def configure_client(monkeypatch, response):
    seen = []

    def create(**kwargs):
        seen.append(kwargs)
        return response

    monkeypatch.setattr("backend.providers.openai_compatible.resolve_api_key", lambda _: "mock-key")
    monkeypatch.setattr(
        "backend.providers.openai_compatible.OpenAI",
        lambda **_: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    return seen


def request(**profile):
    return TextGenerationRequest(
        profile={"base_url": "https://example.com/v1", "model": "mock", **profile},
        system_prompt="system",
        user_prompt="task",
        max_output_tokens=20000,
    )


def test_stream_joins_only_content_and_closes(monkeypatch):
    stream = FakeStream([
        SimpleNamespace(choices=[]),
        chunk(reasoning_content="private reasoning"),
        chunk("<html>"),
        chunk("正文"),
        chunk("</html>"),
        chunk(),
    ])
    seen = configure_client(monkeypatch, stream)

    content = OpenAICompatibleTextProvider().generate_text(request(supports_streaming=True))

    assert content == "<html>正文</html>"
    assert seen[0]["stream"] is True
    assert seen[0]["max_tokens"] == 20000
    assert stream.closed


@pytest.mark.parametrize("profile", [{}, {"supports_streaming": False}, {"supports_streaming": "true"}])
def test_only_explicit_true_enables_streaming(monkeypatch, profile):
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Generated"))])
    seen = configure_client(monkeypatch, response)

    assert OpenAICompatibleTextProvider().generate_text(request(**profile)) == "Generated"
    assert seen[0]["stream"] is False


def test_empty_stream_is_rejected_and_closed(monkeypatch):
    stream = FakeStream([SimpleNamespace(choices=[]), chunk()])
    configure_client(monkeypatch, stream)

    with pytest.raises(ModelProviderError) as error:
        OpenAICompatibleTextProvider().generate_text(request(supports_streaming=True))

    assert error.value.code == "provider_unavailable"
    assert "empty response" in error.value.message
    assert stream.closed


@pytest.mark.parametrize(
    "failure, expected_code",
    [
        (APITimeoutError(request=httpx.Request("POST", "https://example.com/v1")), "provider_timeout"),
        (httpx.ReadTimeout("stream read timed out"), "provider_timeout"),
        (APIConnectionError(request=httpx.Request("POST", "https://example.com/v1")), "provider_unavailable"),
        (RuntimeError("sensitive-provider-detail"), "provider_unavailable"),
    ],
)
def test_stream_iteration_errors_keep_existing_mapping_and_close(monkeypatch, failure, expected_code):
    stream = FakeStream([chunk("partial")], error=failure)
    configure_client(monkeypatch, stream)

    with pytest.raises(ModelProviderError) as error:
        OpenAICompatibleTextProvider().generate_text(request(supports_streaming=True))

    assert error.value.code == expected_code
    assert "sensitive-provider-detail" not in error.value.message
    assert stream.closed
