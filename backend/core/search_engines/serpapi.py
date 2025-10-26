"""SERP API search engine client."""
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import httpx

from backend.core.search_engines.base import (
    SearchEngineBase,
    SearchResult,
    SearchEngineAPIError,
    SearchEngineRateLimitError,
    SearchEngineConfigError,
)

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token bucket algorithm for rate limiting.

    Implements a simple token bucket that refills at a constant rate.
    """

    def __init__(self, rate: int, per: int = 3600):
        """
        Initialize token bucket.

        Args:
            rate: Number of tokens per time period
            per: Time period in seconds (default 3600 = 1 hour)
        """
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.last_update = datetime.now()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = datetime.now()
        elapsed = (now - self.last_update).total_seconds()

        # Calculate tokens to add
        tokens_to_add = (elapsed / self.per) * self.rate

        self.tokens = min(self.rate, self.tokens + tokens_to_add)
        self.last_update = now


class SerpApiClient(SearchEngineBase):
    """
    SERP API client implementation.

    Supports multiple search engines through SERP API:
    - Google
    - Bing
    - DuckDuckGo

    Features:
    - Location/locale targeting
    - Device type (desktop/mobile)
    - Safe search settings
    - Date range filtering
    - Rate limiting with token bucket
    """

    def __init__(
        self,
        api_key: str,
        engine: str = "google",
        location: Optional[str] = None,
        locale: str = "en",
        device: str = "desktop",
        safe_search: bool = True,
        rate_limit: int = 100,
    ):
        """
        Initialize SERP API client.

        Args:
            api_key: SERP API key
            engine: Search engine (google, bing, duckduckgo)
            location: Location for localized results
            locale: Language locale (e.g., 'en', 'da')
            device: Device type (desktop, mobile)
            safe_search: Enable safe search
            rate_limit: Requests per hour
        """
        super().__init__(api_key=api_key)
        self.engine = engine
        self.location = location
        self.locale = locale
        self.device = device
        self.safe_search = safe_search
        self.base_url = "https://serpapi.com/search"

        # Rate limiting
        self.rate_limiter = TokenBucket(rate=rate_limit, per=3600)

        self.validate_config()

    def validate_config(self) -> bool:
        """
        Validate SERP API configuration.

        Returns:
            True if valid

        Raises:
            SearchEngineConfigError: If configuration invalid
        """
        if not self.api_key:
            raise SearchEngineConfigError("SERP API key is required")

        valid_engines = ["google", "bing", "duckduckgo"]
        if self.engine not in valid_engines:
            raise SearchEngineConfigError(
                f"Engine must be one of: {', '.join(valid_engines)}"
            )

        return True

    async def search(
        self,
        query: str,
        max_results: int = 10,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        **kwargs,
    ) -> List[SearchResult]:
        """
        Execute a search query via SERP API.

        Args:
            query: Search query string
            max_results: Maximum number of results
            date_from: Start date for results
            date_to: End date for results
            **kwargs: Additional parameters

        Returns:
            List of SearchResult objects

        Raises:
            SearchEngineRateLimitError: If rate limit exceeded
            SearchEngineAPIError: If API request fails
        """
        # Check rate limit
        if not self.rate_limiter.consume():
            raise SearchEngineRateLimitError(
                f"Rate limit exceeded for SERP API ({self.rate_limiter.rate}/hour)"
            )

        logger.info(f"Executing SERP API search: '{query}' (engine={self.engine})")

        # Build request parameters
        params = self._build_params(
            query=query,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            **kwargs,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise SearchEngineRateLimitError("SERP API rate limit exceeded")
            raise SearchEngineAPIError(f"SERP API request failed: {e}")

        except Exception as e:
            raise SearchEngineAPIError(f"SERP API error: {e}")

        # Parse results
        results = self._parse_results(data)

        logger.info(f"SERP API returned {len(results)} results")
        return results[:max_results]

    async def get_suggestions(self, query: str) -> List[str]:
        """
        Get search suggestions/autocomplete.

        Args:
            query: Partial query string

        Returns:
            List of suggestion strings
        """
        # Check rate limit
        if not self.rate_limiter.consume():
            logger.warning("Rate limit exceeded for suggestions")
            return []

        params = {
            "api_key": self.api_key,
            "engine": f"{self.engine}_autocomplete",
            "q": query,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

            # Extract suggestions based on engine
            suggestions = data.get("suggestions", [])

            if isinstance(suggestions, list):
                if suggestions and isinstance(suggestions[0], dict):
                    # Extract 'value' field if present
                    return [s.get("value", str(s)) for s in suggestions]
                return [str(s) for s in suggestions]

            return []

        except Exception as e:
            logger.warning(f"Could not fetch suggestions: {e}")
            return []

    async def get_related_searches(self, query: str) -> List[str]:
        """
        Get related searches for a query.

        Args:
            query: Search query

        Returns:
            List of related search strings
        """
        # Execute regular search to get related searches
        params = self._build_params(query=query, max_results=10)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

            # Extract related searches
            related = data.get("related_searches", [])

            if isinstance(related, list):
                return [
                    r.get("query", str(r)) if isinstance(r, dict) else str(r)
                    for r in related
                ]

            return []

        except Exception as e:
            logger.warning(f"Could not fetch related searches: {e}")
            return []

    def _build_params(
        self,
        query: str,
        max_results: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Build SERP API request parameters.

        Args:
            query: Search query
            max_results: Maximum results
            date_from: Start date
            date_to: End date
            **kwargs: Additional parameters

        Returns:
            Dict of request parameters
        """
        params = {
            "api_key": self.api_key,
            "engine": self.engine,
            "q": query,
            "num": min(max_results, self.max_results_limit),
        }

        # Add location if specified
        if self.location:
            params["location"] = self.location

        # Add locale
        if self.locale:
            params["hl"] = self.locale

        # Add device type
        if self.device == "mobile":
            params["device"] = "mobile"

        # Add safe search
        if self.safe_search:
            params["safe"] = "active"

        # Add date range (Google specific)
        if self.engine == "google" and (date_from or date_to):
            tbs_parts = []

            if date_from and date_to:
                # Custom date range
                date_from_str = date_from.strftime("%m/%d/%Y")
                date_to_str = date_to.strftime("%m/%d/%Y")
                tbs_parts.append(f"cdr:1,cd_min:{date_from_str},cd_max:{date_to_str}")

            if tbs_parts:
                params["tbs"] = ",".join(tbs_parts)

        return params

    def _parse_results(self, data: Dict[str, Any]) -> List[SearchResult]:
        """
        Parse SERP API response data.

        Args:
            data: Response data from SERP API

        Returns:
            List of SearchResult objects
        """
        results = []

        # Different engines have different response formats
        if self.engine == "google":
            organic_results = data.get("organic_results", [])
        elif self.engine == "bing":
            organic_results = data.get("organic_results", [])
        elif self.engine == "duckduckgo":
            organic_results = data.get("organic_results", [])
        else:
            organic_results = data.get("organic_results", [])

        for idx, result in enumerate(organic_results):
            try:
                url = result.get("link") or result.get("url", "")
                title = result.get("title", "")
                description = result.get("snippet") or result.get("description", "")

                if not url:
                    continue

                # Extract domain
                domain = self._extract_domain(url)

                search_result = SearchResult(
                    url=url,
                    title=title,
                    description=description,
                    rank=idx + 1,
                    domain=domain,
                )

                results.append(search_result)

            except Exception as e:
                logger.warning(f"Could not parse result: {e}")
                continue

        return results

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: URL string

        Returns:
            Domain string
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""

    @property
    def name(self) -> str:
        """Get the name of the search engine."""
        return f"serpapi_{self.engine}"

    @property
    def max_results_limit(self) -> int:
        """Get the maximum number of results this engine can return."""
        # SERP API limits vary by engine
        if self.engine == "google":
            return 100
        elif self.engine == "bing":
            return 50
        elif self.engine == "duckduckgo":
            return 30
        return 100
