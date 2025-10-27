"""Serper API search engine implementation."""
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
    """

    API_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30, **kwargs) -> None:
        """
        Initialize Serper search engine.

        Args:
            api_key: Serper API key
            timeout: Request timeout in seconds
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        self.timeout = timeout

        if not self.api_key:
            raise SearchEngineConfigError("Serper API key is required")

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

        all_results = []
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for page in range(1, pages_needed + 1):
                    # Build request payload for this page
                    payload = {
                        "q": query,
                        "num": results_per_page,
                        "page": page,
                        "gl": gl,
                        "hl": hl,
                    }

                    # Add optional location parameter
                    if "location" in kwargs:
                        payload["location"] = kwargs["location"]

                    logger.debug(f"Fetching page {page}/{pages_needed} for query: {query}")

                    response = await client.post(
                        self.API_URL,
                        json=payload,
                        headers=headers,
                    )

                    # Handle rate limiting
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

                    # Parse results from this page
                    organic_results = data.get("organic", [])

                    if not organic_results:
                        logger.info(f"No more results found on page {page} for query: {query}")
                        break  # No more results available

                    for result in organic_results:
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

                        search_result = SearchResult(
                            url=url,
                            title=title,
                            description=snippet,
                            rank=len(all_results) + 1,
                            domain=self._extract_domain(url),
                        )
                        all_results.append(search_result)

                    # Stop if we've reached max_results
                    if len(all_results) >= max_results:
                        break

                logger.info(
                    f"Serper search for '{query}' returned {len(all_results)} results "
                    f"from {page} page(s) (gl={gl}, hl={hl})"
                )
                return all_results

        except httpx.TimeoutException:
            error_msg = f"Serper API request timed out after {self.timeout} seconds"
            logger.error(error_msg)
            raise SearchEngineAPIError(error_msg)

        except httpx.HTTPError as e:
            error_msg = f"Serper API HTTP error: {str(e)}"
            logger.error(error_msg)
            raise SearchEngineAPIError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during Serper search: {str(e)}"
            logger.error(error_msg)
            raise SearchEngineAPIError(error_msg)

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
