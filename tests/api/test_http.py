"""Behavior of the plugin HTTP client, driven through an in-memory transport."""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from toon.api.http import (
    BasicAuth,
    BearerAuth,
    HeaderAuth,
    HttpClient,
    HttpError,
    HttpResponse,
    NetrcAuth,
)

Handler = Callable[[httpx.Request], httpx.Response]


def _capturing_transport(requests: list[httpx.Request]) -> httpx.MockTransport:
    """A transport that records each request and answers ``200 ok``."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="ok")

    return httpx.MockTransport(handler)


def _basic(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode("ascii")


# --- authentication ----------------------------------------------------------


async def test_basic_auth_sets_the_authorization_header() -> None:
    requests: list[httpx.Request] = []
    client = HttpClient(
        "https://ci.example.com",
        auth=BasicAuth("alice", "s3cret"),
        transport=_capturing_transport(requests),
    )

    async with client:
        await client.get("/job")

    assert requests[0].headers["Authorization"] == _basic("alice", "s3cret")


async def test_bearer_auth_sets_the_authorization_header() -> None:
    requests: list[httpx.Request] = []
    client = HttpClient(
        "https://api.example.com",
        auth=BearerAuth("token-123"),
        transport=_capturing_transport(requests),
    )

    async with client:
        await client.get("/me")

    assert requests[0].headers["Authorization"] == "Bearer token-123"


async def test_header_auth_sets_the_configured_header() -> None:
    requests: list[httpx.Request] = []
    client = HttpClient(
        "https://api.example.com",
        auth=HeaderAuth("X-Api-Key", "key-abc"),
        transport=_capturing_transport(requests),
    )

    async with client:
        await client.get("/things")

    assert requests[0].headers["X-Api-Key"] == "key-abc"
    assert "Authorization" not in requests[0].headers


async def test_netrc_auth_authenticates_only_the_matching_host(tmp_path: Path) -> None:
    netrc_file = tmp_path / "netrc"
    netrc_file.write_text("machine ci.example.com login alice password s3cret\n", encoding="utf-8")
    netrc_file.chmod(0o600)
    requests: list[httpx.Request] = []
    transport = _capturing_transport(requests)

    async with HttpClient(
        "https://ci.example.com", auth=NetrcAuth(netrc_file), transport=transport
    ) as client:
        await client.get("/job")
    async with HttpClient(
        "https://other.example.com", auth=NetrcAuth(netrc_file), transport=transport
    ) as client:
        await client.get("/job")

    assert requests[0].headers["Authorization"] == _basic("alice", "s3cret")
    assert "Authorization" not in requests[1].headers


# --- requests and responses --------------------------------------------------


async def test_base_url_is_joined_with_a_relative_path() -> None:
    requests: list[httpx.Request] = []
    client = HttpClient("https://api.example.com/", transport=_capturing_transport(requests))

    async with client:
        await client.get("/things")

    assert str(requests[0].url) == "https://api.example.com/things"


async def test_get_json_parses_the_body() -> None:
    payload = {"jobs": [{"name": "build"}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = HttpClient("https://api.example.com", transport=httpx.MockTransport(handler))

    async with client:
        data = await client.get_json("/api/json")

    assert data == payload


async def test_non_2xx_status_raises_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not here")

    client = HttpClient("https://api.example.com", transport=httpx.MockTransport(handler))

    with pytest.raises(HttpError) as excinfo:
        async with client:
            await client.get("/missing")

    assert excinfo.value.status_code == 404
    assert excinfo.value.body == "not here"


async def test_raise_for_status_false_returns_the_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = HttpClient(
        "https://api.example.com",
        transport=httpx.MockTransport(handler),
        raise_for_status=False,
    )

    async with client:
        response = await client.get("/broken")

    assert isinstance(response, HttpResponse)
    assert response.status_code == 500
    assert response.ok is False
    assert response.text == "boom"


async def test_raise_for_status_can_be_overridden_per_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="later")

    client = HttpClient("https://api.example.com", transport=httpx.MockTransport(handler))

    async with client:
        returned = await client.get("/broken", raise_for_status=False)

        assert returned.status_code == 503
        with pytest.raises(HttpError):
            await client.get("/broken")
