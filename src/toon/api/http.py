"""Async HTTP client for plugins.

A small, authenticated wrapper over :mod:`httpx`, exposed on the public API so
plugins can call external services (Jenkins, Gerrit, anything using
``~/.netrc``, ...).

Authentication lives in a **separate, pluggable** :class:`Auth` object: the
client carries no credential logic. Swap :class:`BasicAuth` for
:class:`NetrcAuth` and nothing else changes.

Importing this module pulls in httpx; ``toon.api`` re-exports these names
lazily, so the core runtime never imports httpx.

Typical use::

    from toon.api import BasicAuth, HttpClient

    async with HttpClient("https://ci.example.com", auth=BasicAuth(user, token)) as api:
        data = await api.get_json("/api/json")
        running = sum(1 for job in data["jobs"] if job.get("color", "").endswith("_anime"))
"""

from __future__ import annotations

import base64
import json
import netrc
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

__all__ = [
    "Auth",
    "BasicAuth",
    "BearerAuth",
    "HeaderAuth",
    "HttpClient",
    "HttpError",
    "HttpResponse",
    "NetrcAuth",
    "NoAuth",
]

_DEFAULT_TIMEOUT = 30.0


class HttpError(Exception):
    """Raised when a response status is not successful (by default)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str = "",
        body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.body = body


@runtime_checkable
class Auth(Protocol):
    """Supplies credentials for a request.

    Implementations add whatever is needed to ``request`` (typically an
    ``Authorization`` header, but any header/param is allowed). Keep them
    stateless or cheap; ``apply`` is called for every request.
    """

    async def apply(self, request: httpx.Request) -> None:
        """Attach credentials to ``request`` in place."""


class NoAuth:
    """The default: attach nothing."""

    async def apply(self, request: httpx.Request) -> None:
        """Do nothing."""
        return None


def _basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


class BasicAuth:
    """HTTP Basic auth — Jenkins (user + API token), Gerrit (user + password)."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def apply(self, request: httpx.Request) -> None:
        """Set the ``Authorization: Basic`` header."""
        request.headers["Authorization"] = _basic_header(self._username, self._password)


class BearerAuth:
    """``Authorization: Bearer <token>`` auth."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def apply(self, request: httpx.Request) -> None:
        """Set the ``Authorization: Bearer`` header."""
        request.headers["Authorization"] = f"Bearer {self._token}"


class HeaderAuth:
    """Auth via an arbitrary header, e.g. an API key (``X-Api-Key``)."""

    def __init__(self, header: str, value: str) -> None:
        self._header = header
        self._value = value

    async def apply(self, request: httpx.Request) -> None:
        """Set the configured header."""
        request.headers[self._header] = self._value


class NetrcAuth:
    """Basic auth from ``~/.netrc`` (or an explicit netrc file).

    Credentials are looked up per request host and cached. If the host has no
    entry, the request is left unauthenticated.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._cache: dict[str, tuple[str, str] | None] = {}

    async def apply(self, request: httpx.Request) -> None:
        """Set a Basic header if the request host has a netrc entry."""
        credentials = self._credentials(request.url.host)
        if credentials is not None and "Authorization" not in request.headers:
            request.headers["Authorization"] = _basic_header(*credentials)

    def _credentials(self, host: str) -> tuple[str, str] | None:
        if host in self._cache:
            return self._cache[host]
        result: tuple[str, str] | None = None
        try:
            parsed = netrc.netrc(str(self._path) if self._path else None)
            auth = parsed.authenticators(host)
            if auth is not None:
                login, _account, password = auth
                if login and password:
                    result = (login, password)
        except (OSError, netrc.NetrcParseError):
            result = None
        self._cache[host] = result
        return result


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A small, decoupled view of an HTTP response."""

    status_code: int
    url: str
    headers: Mapping[str, str]
    text: str

    @property
    def ok(self) -> bool:
        """Whether the status is in the 2xx range."""
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        """Parse the body as JSON."""
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        """Raise :class:`HttpError` when the status is not successful."""
        if not self.ok:
            raise HttpError(
                f"HTTP {self.status_code} for {self.url}",
                status_code=self.status_code,
                url=self.url,
                body=self.text,
            )


def _wrap(response: httpx.Response) -> HttpResponse:
    return HttpResponse(
        status_code=response.status_code,
        url=str(response.url),
        headers=dict(response.headers),
        text=response.text,
    )


class HttpClient:
    """An async, authenticated HTTP client.

    Use it as an async context manager (or call :meth:`aclose`) so the
    underlying connection pool is released::

        async with HttpClient("https://gerrit.example.com", auth=BasicAuth(u, p)) as api:
            changes = await api.get_json("/changes/?q=owner:self")

    By default a non-2xx response raises :class:`HttpError`; pass
    ``raise_for_status=False`` (on the client or per call) to inspect it instead.
    """

    def __init__(
        self,
        base_url: str = "",
        *,
        auth: Auth | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        follow_redirects: bool = True,
        raise_for_status: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._auth: Auth = auth if auth is not None else NoAuth()
        self._raise_for_status = raise_for_status
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=dict(headers or {}),
            timeout=timeout,
            follow_redirects=follow_redirects,
            event_hooks={"request": [self._auth.apply]},
            transport=transport,
        )

    # --- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying client and release connections."""
        await self._client.aclose()

    # --- requests ----------------------------------------------------------

    async def request(
        self,
        method: str,
        url: str,
        *,
        raise_for_status: bool | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Send a request and return a wrapped response."""
        response = _wrap(await self._client.request(method, url, **kwargs))
        should_raise = self._raise_for_status if raise_for_status is None else raise_for_status
        if should_raise:
            response.raise_for_status()
        return response

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        """Send a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        """Send a POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> HttpResponse:
        """Send a PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> HttpResponse:
        """Send a PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> HttpResponse:
        """Send a DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        """GET ``url`` and parse the body as JSON."""
        return (await self.get(url, **kwargs)).json()

    async def post_json(self, url: str, **kwargs: Any) -> Any:
        """POST ``url`` (pass ``json=...``) and parse the body as JSON."""
        return (await self.post(url, **kwargs)).json()
