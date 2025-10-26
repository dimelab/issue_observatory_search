"""Google Custom Search API implementation."""
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

from backend.core.search_engines.base import (
    SearchEngineBase,
    SearchResult,
    SearchEngineConfigError,
    SearchEngineAPIError,
    SearchEngineRateLimitError,
)

logger = logging.getLogger(__name__)


class GoogleCustomSearch(SearchEngineBase):
    """Google Custom Search API implementation."""

    BASE_URL = "https://www.googleapis.com/customsearch/v1"
    MAX_RESULTS_PER_REQUEST = 10  # Google CSE limit
    MAX_TOTAL_RESULTS = 100  # Google CSE daily limit

    def __init__(
        self,
        api_key: str,
        search_engine_id: str,
        timeout: int = 30,
        **kwargs
    ) -> None:
        """
        Initialize Google Custom Search.

        Args:
            api_key: Google API key
            search_engine_id: Custom Search Engine ID
            timeout: Request timeout in seconds
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        self.search_engine_id = search_engine_id
        self.timeout = timeout
        self.validate_config()

    def validate_config(self) -> bool:
        """
        Validate configuration.

        Returns:
            bool: True if valid

        Raises:
            SearchEngineConfigError: If configuration is invalid
        """
        if not self.api_key:
            raise SearchEngineConfigError("Google API key is required")
        if not self.search_engine_id:
            raise SearchEngineConfigError("Search Engine ID is required")
        return True

    @property
    def name(self) -> str:
        """Get engine name."""
        return "google_custom"

    @property
    def max_results_limit(self) -> int:
        """Get maximum results limit."""
        return self.MAX_TOTAL_RESULTS

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> list[SearchResult]:
        """
        Execute a Google Custom Search.

        Args:
            query: Search query string
            max_results: Maximum number of results (max 100)
            **kwargs: Additional parameters (e.g., lr for language, cr for country)

        Returns:
            list[SearchResult]: List of search results

        Raises:
            SearchEngineAPIError: If API request fails
            SearchEngineRateLimitError: If rate limit exceeded
        """
        if max_results > self.MAX_TOTAL_RESULTS:
            logger.warning(
                f"Requested {max_results} results, limiting to {self.MAX_TOTAL_RESULTS}"
            )
            max_results = self.MAX_TOTAL_RESULTS

        results = []
        start_index = 1

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while len(results) < max_results:
                # Calculate how many results to fetch in this request
                num_results = min(
                    max_results - len(results),
                    self.MAX_RESULTS_PER_REQUEST
                )

                params = {
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "q": query,
                    "num": num_results,
                    "start": start_index,
                }

                # Add any additional parameters
                params.update(kwargs)

                try:
                    response = await client.get(self.BASE_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        raise SearchEngineRateLimitError(
                            "Google Custom Search rate limit exceeded"
                        )
                    elif e.response.status_code == 403:
                        error_data = e.response.json()
                        error_message = error_data.get("error", {}).get("message", "")
                        if "quota" in error_message.lower():
                            raise SearchEngineRateLimitError(
                                f"Google Custom Search quota exceeded: {error_message}"
                            )
                        raise SearchEngineAPIError(
                            f"Google Custom Search API error: {error_message}"
                        )
                    else:
                        raise SearchEngineAPIError(
                            f"Google Custom Search HTTP error: {e.response.status_code}"
                        )
                except httpx.RequestError as e:
                    raise SearchEngineAPIError(
                        f"Google Custom Search request error: {str(e)}"
                    )

                # Parse results
                items = data.get("items", [])
                if not items:
                    # No more results available
                    break

                for item in items:
                    url = item.get("link", "")
                    domain = self._extract_domain(url)

                    result = SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        description=item.get("snippet", ""),
                        rank=len(results) + 1,
                        domain=domain,
                    )
                    results.append(result)

                # Check if we have more results to fetch
                search_info = data.get("searchInformation", {})
                total_results = int(search_info.get("totalResults", 0))

                if len(results) >= total_results or len(results) >= max_results:
                    break

                # Move to next page
                start_index += num_results

        logger.info(
            f"Google Custom Search: Retrieved {len(results)} results for query '{query}'"
        )
        return results

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            str: Domain name
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.path
        except Exception:
            return ""
