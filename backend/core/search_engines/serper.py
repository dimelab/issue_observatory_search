"""Serper API search engine implementation."""
import asyncio
import contextlib
import logging
import random
from collections.abc import Mapping
from typing import Optional
from urllib.parse import urlparse

import httpx

from backend.core.concurrency import RedisLimits
from backend.core.search_engines.base import (
    SearchEngineBase,
    SearchResult,
    SearchEngineError,
    SearchEngineConfigError,
    SearchEngineAPIError,
    SearchEngineRateLimitError,
    is_google_redirect,
)

logger = logging.getLogger(__name__)


class SerperSearch(SearchEngineBase):
    """
    Serper API search engine implementation.

    Serper (google.serper.dev) provides a cost-effective Google Search API.
    Pricing: ~$2 per 1000 searches (much cheaper than Google Custom Search).

    Features:
    - Google search results via API
    - Simple JSON API
    - Fast response times
    - No search engine setup required
    - Supports pagination

    Google returns result links beyond the top three as google.com/goto
    redirects. Serper resolves the top three itself; the rest are resolved here
    by sending each page of the search response to Serper's /resolve endpoint
    (free, but it waits for Google, about 30 seconds right after a search). A
    link that stays unresolved is dropped, never returned as if it were a page.
    """

    API_URL = "https://google.serper.dev/search"
    RESOLVE_URL = "https://google.serper.dev/resolve"
    RESOLVE_TIMEOUT = 120.0  # seconds per /resolve request; it waits for Google
    RESOLVE_MAX_ATTEMPTS = 3  # /resolve answers with retryAfter while links are not ready
    RESOLVE_MAX_WAIT = 60.0  # longest pause between two attempts, seconds
    RATE_LIMIT_RETRIES = 3  # a 429 is waited out and asked again this many times
    RATE_LIMIT_BASE_WAIT = 2.0  # first wait without a Retry-After header; doubles each time

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 2,
        resolve_concurrency: int = 30,
        base_url: Optional[str] = None,
        limits: Optional[RedisLimits] = None,
        rate_per_second: int = 40,
        **kwargs
    ) -> None:
        """
        Initialize Serper search engine.

        Args:
            api_key: Serper API key
            timeout: Request timeout in seconds (default: 60 for complex queries)
            max_retries: Maximum number of retries on timeout (default: 2)
            resolve_concurrency: How many /resolve requests may be in flight at
                once across all searches made with this instance, and (with
                limits) across all processes; each one waits about 30 seconds
                for Google
            base_url: Serper's address, if not the real one (for tests)
            limits: Cross-process limits (Redis). Without them only this
                instance's own limits apply
            rate_per_second: Requests per second allowed across all processes
                (with limits)
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        self.timeout = timeout
        self.max_retries = max_retries
        self.resolve_concurrency = max(1, resolve_concurrency)
        self._resolve_slots: Optional[asyncio.Semaphore] = None
        self.limits_shared = limits
        self.rate_per_second = rate_per_second
        if base_url:
            self.API_URL = base_url.rstrip("/") + "/search"
            self.RESOLVE_URL = base_url.rstrip("/") + "/resolve"

        if not self.api_key:
            raise SearchEngineConfigError("Serper API key is required")

        # Configure timeout once (reused by persistent client)
        self.timeout_config = httpx.Timeout(
            timeout=self.timeout,
            connect=30.0,  # Generous for DNS + TLS handshake
            read=self.timeout,
            write=15.0,
            pool=120.0  # concurrency is limited by semaphores, not by waiting for a connection
        )

        # Configure connection limits: every /resolve in flight keeps its connection
        # for about 30 seconds, and searches need connections beside them
        self.limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=max(100, self.resolve_concurrency + 50),
            keepalive_expiry=30.0
        )

        # Persistent HTTP client for connection reuse
        self._client: Optional[httpx.AsyncClient] = None

    def validate_config(self) -> bool:
        """
        Validate Serper configuration.

        Returns:
            bool: True if configuration is valid

        Raises:
            SearchEngineConfigError: If configuration is invalid
        """
        if not self.api_key or not isinstance(self.api_key, str):
            raise SearchEngineConfigError("Valid Serper API key is required")
        return True

    @property
    def name(self) -> str:
        """Get the name of the search engine."""
        return "serper"

    @property
    def max_results_limit(self) -> int:
        """
        Get the maximum number of results this engine can return.

        Serper supports up to 100 results per request.
        """
        return 100

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create the persistent HTTP client.

        Returns:
            httpx.AsyncClient: The HTTP client instance
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_config,
                limits=self.limits,
                http2=False,  # Disable HTTP/2 to avoid potential issues
                follow_redirects=True
            )
            logger.debug("Created new persistent httpx client for Serper")
        return self._client

    async def close(self) -> None:
        """
        Close the HTTP client and release resources.

        Call this when done using the search engine to properly cleanup.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("Closed persistent httpx client for Serper")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: URL to extract domain from

        Returns:
            str: Domain name
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return ""

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> list[SearchResult]:
        """
        Execute a search query using Serper API with pagination.

        Args:
            query: Search query string
            max_results: Maximum number of results to return (up to 100)
            **kwargs: Additional search parameters:
                - location: Geographic location (e.g., "Denmark")
                - gl: Country code (e.g., "dk" - defaults to Denmark)
                - hl: Language code (e.g., "da" - defaults to Danish)
                - num: Number of results per page (default: 10, max: 10)

        Returns:
            list[SearchResult]: List of search results

        Raises:
            SearchEngineAPIError: If API request fails
            SearchEngineRateLimitError: If rate limit is exceeded
        """
        if max_results > self.max_results_limit:
            logger.warning(
                f"Requested {max_results} results but max is {self.max_results_limit}, "
                f"capping at {self.max_results_limit}"
            )
            max_results = self.max_results_limit

        # Set Danish defaults
        gl = kwargs.get("gl", "dk")  # Default to Denmark
        hl = kwargs.get("hl", "da")  # Default to Danish

        # Serper returns max 10 results per page, so we need to paginate
        results_per_page = 10
        pages_needed = (max_results + results_per_page - 1) // results_per_page  # Ceiling division

        pages: list[dict] = []  # raw search responses, resolved after the loop
        fetched = 0  # results with a link and a title seen so far
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        logger.debug(f"Serper search starting with timeout={self.timeout}s for query: {query}")

        # Get persistent client (reuses connections across searches)
        client = await self._get_client()

        try:
            for page in range(1, pages_needed + 1):
                # Build request payload for this page
                payload = {
                    "q": query,
                    "num": results_per_page,
                    "page": page,
                    "gl": gl,
                    "hl": hl,
                }

                # Log the exact payload being sent for debugging
                logger.info(
                    f"Serper API payload: q={repr(query)}, "
                    f"num={results_per_page}, page={page}, gl={gl}, hl={hl}"
                )

                # Add optional location parameter
                if "location" in kwargs:
                    payload["location"] = kwargs["location"]

                logger.info(
                    f"Fetching page {page}/{pages_needed} for query '{query}' "
                    f"(timeout={self.timeout}s, has_api_key={bool(self.api_key)})"
                )

                # Retry logic for timeouts
                retry_count = 0
                response = None
                last_error = None

                while retry_count <= self.max_retries:
                    try:
                        import time
                        start_time = time.time()
                        logger.info(
                            f"Attempt {retry_count + 1}/{self.max_retries + 1} for query: {query[:50]}... "
                            f"(POST to {self.API_URL})"
                        )
                        await self._throttle()
                        response = await client.post(
                            self.API_URL,
                            json=payload,
                            headers=headers,
                        )
                        elapsed = time.time() - start_time
                        logger.info(
                            f"Request successful on attempt {retry_count + 1} "
                            f"(took {elapsed:.2f}s, status={response.status_code})"
                        )
                        break  # Success, exit retry loop

                    except httpx.TimeoutException as e:
                        retry_count += 1
                        last_error = e
                        if retry_count <= self.max_retries:
                            wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                            logger.warning(
                                f"Timeout on attempt {retry_count}/{self.max_retries + 1} "
                                f"for query '{query}', retrying in {wait_time}s..."
                            )
                            import asyncio
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(
                                f"Failed after {retry_count} attempts for query: {query}"
                            )
                            raise SearchEngineAPIError(
                                f"Serper API timed out after {self.timeout}s and {self.max_retries} retries. "
                                f"Try simplifying your query or increasing timeout."
                            )

                if response is None:
                    raise SearchEngineAPIError("Failed to get response from Serper API")

                # Handle rate limiting: wait and ask again before giving up
                rate_limited = 0
                while (
                    response.status_code == 429
                    and rate_limited < self.RATE_LIMIT_RETRIES
                ):
                    rate_limited += 1
                    await self._wait_after_rate_limit(response, rate_limited, "search")
                    await self._throttle()
                    response = await client.post(
                        self.API_URL, json=payload, headers=headers
                    )

                if response.status_code == 429:
                    error_msg = "Serper API rate limit exceeded"
                    logger.error(error_msg)
                    raise SearchEngineRateLimitError(error_msg)

                # Handle authentication errors
                if response.status_code == 401:
                    error_msg = "Invalid Serper API key"
                    logger.error(error_msg)
                    raise SearchEngineAPIError(error_msg)

                # Handle other errors
                if response.status_code != 200:
                    error_msg = f"Serper API request failed with status {response.status_code}"
                    logger.error(f"{error_msg}: {response.text}")
                    raise SearchEngineAPIError(error_msg)

                data = response.json()

                # Keep the raw page; links are resolved and parsed after the loop
                organic_results = data.get("organic", [])

                if not organic_results:
                    logger.info(f"No more results found on page {page} for query: {query}")
                    break  # No more results available

                pages.append(data)
                fetched += sum(
                    1 for result in organic_results
                    if result.get("link") and result.get("title")
                )

                # Stop if we've reached max_results
                if fetched >= max_results:
                    break

            # Beyond the top three, Google returns redirect links: resolve them
            pages = await self._resolve_pages(pages, query)

            all_results: list[SearchResult] = []
            unresolved = 0
            for data in pages:
                for result in data.get("organic", []):
                    # Stop if we've reached max_results
                    if len(all_results) >= max_results:
                        break

                    # Extract result data
                    url = result.get("link", "")
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")

                    if not url or not title:
                        logger.debug(f"Skipping result due to missing URL or title")
                        continue

                    if is_google_redirect(url):
                        unresolved += 1
                        continue

                    search_result = SearchResult(
                        url=url,
                        title=title,
                        description=snippet,
                        rank=len(all_results) + 1,
                        domain=self._extract_domain(url),
                    )
                    all_results.append(search_result)

                if len(all_results) >= max_results:
                    break

            if unresolved:
                logger.warning(
                    f"Serper search for '{query}': dropped {unresolved} result(s) "
                    f"whose Google redirect link could not be resolved"
                )

            logger.info(
                f"Serper search for '{query}' returned {len(all_results)} results "
                f"from {page} page(s) (gl={gl}, hl={hl})"
            )
            return all_results

        except httpx.TimeoutException:
            error_msg = (
                f"Serper API request timed out after {self.timeout} seconds. "
                f"Complex queries with operators may take longer. Try simplifying the query."
            )
            logger.error(error_msg)
            raise SearchEngineAPIError(error_msg)

        except httpx.HTTPError as e:
            error_msg = f"Serper API HTTP error: {str(e)}"
            logger.error(error_msg)
            raise SearchEngineAPIError(error_msg)

        except SearchEngineError:
            raise  # already a clear message (rate limit, bad key, /resolve failure)

        except Exception as e:
            error_msg = f"Unexpected error during Serper search: {str(e)}"
            logger.error(error_msg)
            raise SearchEngineAPIError(error_msg)

    @staticmethod
    def _has_google_redirects(data: dict) -> bool:
        """Whether a search response still has a Google redirect among its organic links."""
        return any(
            is_google_redirect(result.get("link", ""))
            for result in data.get("organic", [])
        )

    async def _throttle(self) -> None:
        """Wait for a place in the requests-per-second budget shared by all processes."""
        if self.limits_shared is not None:
            await self.limits_shared.throttle("serper", self.rate_per_second)

    def _global_resolve_slot(self):
        """
        The limit on /resolve requests in flight across all processes (a no-op
        without shared limits). Leased for longer than a request can take.
        """
        if self.limits_shared is None:
            return contextlib.nullcontext()
        return self.limits_shared.slot(
            "serper-resolve",
            self.resolve_concurrency,
            lease=self.RESOLVE_TIMEOUT + 60.0,
        )

    def _get_resolve_slots(self) -> asyncio.Semaphore:
        """The limit on /resolve requests in flight, created inside the running loop."""
        if self._resolve_slots is None:
            self._resolve_slots = asyncio.Semaphore(self.resolve_concurrency)
        return self._resolve_slots

    async def _wait_after_rate_limit(
        self, response: httpx.Response, attempt: int, endpoint: str
    ) -> None:
        """
        Pause after a 429 answer: the Retry-After header if there is one, else
        a doubling wait with some jitter so parallel searches do not all ask
        again at the same moment. Never longer than RESOLVE_MAX_WAIT.

        Args:
            response: The 429 response
            attempt: Which retry this is, starting at 1
            endpoint: Name of the endpoint, for the log
        """
        headers = getattr(response, "headers", None)
        header = headers.get("Retry-After") if isinstance(headers, Mapping) else None
        try:
            wait = float(header)
        except (TypeError, ValueError):
            wait = (
                self.RATE_LIMIT_BASE_WAIT
                * 2 ** (attempt - 1)
                * (1 + random.random() * 0.5)
            )
        wait = min(wait, self.RESOLVE_MAX_WAIT)
        logger.warning(
            f"Serper {endpoint}: rate limit hit, waiting {wait:.1f}s "
            f"(retry {attempt}/{self.RATE_LIMIT_RETRIES})"
        )
        await asyncio.sleep(wait)

    async def _resolve_pages(self, pages: list[dict], query: str) -> list[dict]:
        """
        Resolve the Google redirect links of every page that has some.

        The pages are resolved at the same time, so a keyword costs one wait
        for Google rather than one per page.

        Args:
            pages: Raw search responses
            query: Query text, for log messages

        Returns:
            list[dict]: The pages, in order, with the real URLs filled in

        Raises:
            SearchEngineAPIError: If /resolve fails or times out
            SearchEngineRateLimitError: If /resolve's rate limit is hit
        """
        wanted = [i for i, data in enumerate(pages) if self._has_google_redirects(data)]
        if not wanted:
            return pages

        logger.info(
            f"Serper search for '{query}': resolving Google links on "
            f"{len(wanted)} of {len(pages)} page(s)"
        )
        outcomes = await asyncio.gather(
            *(self._resolve_links(pages[i]) for i in wanted),
            return_exceptions=True,
        )
        # Every page has finished by now; report the first failure, if any
        resolved = list(pages)
        for i, outcome in zip(wanted, outcomes):
            if isinstance(outcome, BaseException):
                raise outcome
            resolved[i] = outcome
        return resolved

    async def _resolve_links(self, data: dict) -> dict:
        """
        Send one search response to Serper's /resolve and return it with the
        real URLs.

        While Google is not ready, some links stay redirects and the response
        carries retryAfter (seconds); the answer is sent again after that wait,
        up to RESOLVE_MAX_ATTEMPTS times. Links still unresolved after that are
        left for the caller to drop.

        Args:
            data: Search response for one page

        Returns:
            dict: The response, with as many links resolved as Google allowed

        Raises:
            SearchEngineAPIError: If /resolve answers with an error or times out
            SearchEngineRateLimitError: If /resolve's rate limit is hit
        """
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        current: dict = data
        not_ready = 0
        rate_limited = 0

        while True:
            try:
                async with self._get_resolve_slots(), self._global_resolve_slot():
                    await self._throttle()
                    response = await client.post(
                        self.RESOLVE_URL,
                        json=current,
                        headers=headers,
                        timeout=httpx.Timeout(self.RESOLVE_TIMEOUT, connect=30.0),
                    )
            except httpx.TimeoutException:
                raise SearchEngineAPIError(
                    f"Serper /resolve timed out after {self.RESOLVE_TIMEOUT:.0f}s "
                    f"while resolving Google links"
                )
            except httpx.HTTPError as e:
                raise SearchEngineAPIError(f"Serper /resolve HTTP error: {e}")

            if response.status_code == 429:
                rate_limited += 1
                if rate_limited > self.RATE_LIMIT_RETRIES:
                    raise SearchEngineRateLimitError("Serper /resolve rate limit exceeded")
                await self._wait_after_rate_limit(response, rate_limited, "/resolve")
                continue
            if response.status_code == 401:
                raise SearchEngineAPIError("Invalid Serper API key")
            if response.status_code != 200:
                logger.error(
                    f"Serper /resolve failed with status {response.status_code}: "
                    f"{response.text}"
                )
                raise SearchEngineAPIError(
                    f"Serper /resolve failed with status {response.status_code}"
                )

            current = response.json()
            retry_after = current.pop("retryAfter", None)
            if not self._has_google_redirects(current):
                return current
            not_ready += 1
            if not_ready >= self.RESOLVE_MAX_ATTEMPTS:
                return current

            try:
                wait = min(float(retry_after), self.RESOLVE_MAX_WAIT)
            except (TypeError, ValueError):
                wait = 0.0
            logger.info(
                f"Serper /resolve: some links not ready, retrying in {wait:.0f}s "
                f"(attempt {not_ready}/{self.RESOLVE_MAX_ATTEMPTS})"
            )
            await asyncio.sleep(wait)

    async def get_search_metadata(self, query: str) -> dict:
        """
        Get metadata about search results (total results, related searches, etc.).

        Args:
            query: Search query string

        Returns:
            dict: Metadata including searchParameters, knowledgeGraph, relatedSearches, etc.
        """
        payload = {
            "q": query,
            "num": 10,  # Just get metadata, don't need many results
        }

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                metadata = {
                    "search_parameters": data.get("searchParameters", {}),
                    "knowledge_graph": data.get("knowledgeGraph", {}),
                    "related_searches": data.get("relatedSearches", []),
                    "people_also_ask": data.get("peopleAlsoAsk", []),
                }

                return metadata

        except Exception as e:
            logger.error(f"Error getting search metadata: {str(e)}")
            return {}
