"""Abstract base class for search engines."""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

# google.com, www.google.com, google.co.uk, www.google.dk, ...
_GOOGLE_HOST = re.compile(r"^(www\.)?google\.[a-z]{2,3}(\.[a-z]{2})?$")


def is_google_redirect(url: str) -> bool:
    """
    Whether a result link is a Google redirect (google.com/goto?url=...) rather
    than the page itself.

    Google returns these for result links on searches made without a Google
    account; the real address is inside the link and cannot be read from it. A
    search engine client has to resolve them (see SerperSearch) and nothing
    should store, deduplicate or scrape them as if they were the page.

    Args:
        url: Link taken from a search response

    Returns:
        bool: True for a link on a Google domain whose path starts with /goto
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return bool(_GOOGLE_HOST.match(host)) and parsed.path.startswith("/goto")


@dataclass
class SearchResult:
    """Search result data class."""

    url: str
    title: str
    description: Optional[str]
    rank: int
    domain: str


class SearchEngineBase(ABC):
    """Abstract base class for search engine implementations."""

    def __init__(self, api_key: Optional[str] = None, **kwargs) -> None:
        """
        Initialize search engine.

        Args:
            api_key: API key for the search engine
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> list[SearchResult]:
        """
        Execute a search query.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional search parameters

        Returns:
            list[SearchResult]: List of search results

        Raises:
            SearchEngineError: If search fails
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate search engine configuration.

        Returns:
            bool: True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of the search engine."""
        pass

    @property
    @abstractmethod
    def max_results_limit(self) -> int:
        """Get the maximum number of results this engine can return."""
        pass


class SearchEngineError(Exception):
    """Base exception for search engine errors."""

    pass


class SearchEngineConfigError(SearchEngineError):
    """Exception raised for configuration errors."""

    pass


class SearchEngineAPIError(SearchEngineError):
    """Exception raised for API errors."""

    pass


class SearchEngineRateLimitError(SearchEngineError):
    """Exception raised when rate limit is exceeded."""

    pass
