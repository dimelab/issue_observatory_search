"""Robots.txt checker with caching for polite web scraping."""
import logging
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import httpx

logger = logging.getLogger(__name__)


class RobotsCache:
    """
    Cache for robots.txt files with expiration.

    Stores parsed robots.txt data in memory with a TTL to avoid
    repeated fetches of the same robots.txt files.
    """

    def __init__(self, ttl_minutes: int = 60):
        """
        Initialize the robots.txt cache.

        Args:
            ttl_minutes: Time-to-live for cached entries in minutes
        """
        self._cache: dict[str, tuple[RobotFileParser, datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get(self, domain: str) -> Optional[RobotFileParser]:
        """
        Get cached robots.txt parser for a domain.

        Args:
            domain: The domain to look up

        Returns:
            RobotFileParser if cached and not expired, None otherwise
        """
        if domain in self._cache:
            parser, cached_at = self._cache[domain]
            if datetime.utcnow() - cached_at < self._ttl:
                return parser
            else:
                # Expired, remove from cache
                del self._cache[domain]
        return None

    def set(self, domain: str, parser: RobotFileParser) -> None:
        """
        Cache a robots.txt parser for a domain.

        Args:
            domain: The domain to cache for
            parser: The RobotFileParser to cache
        """
        self._cache[domain] = (parser, datetime.utcnow())

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def remove(self, domain: str) -> None:
        """
        Remove a specific domain from the cache.

        Args:
            domain: The domain to remove
        """
        if domain in self._cache:
            del self._cache[domain]


class RobotsChecker:
    """
    Robots.txt checker that respects robots exclusion protocol.

    Features:
    - Caching of robots.txt files to reduce network requests
    - Graceful handling of missing robots.txt (allows by default)
    - Support for custom user agents
    - Proper URL parsing and normalization
    """

    def __init__(
        self,
        user_agent: str = "IssueObservatoryBot/1.0",
        cache_ttl_minutes: int = 60,
        timeout: int = 10,
    ):
        """
        Initialize the robots.txt checker.

        Args:
            user_agent: User agent string to identify the bot
            cache_ttl_minutes: How long to cache robots.txt files (minutes)
            timeout: Timeout for fetching robots.txt (seconds)
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache = RobotsCache(ttl_minutes=cache_ttl_minutes)

    def _get_robots_url(self, url: str) -> str:
        """
        Get the robots.txt URL for a given URL.

        Args:
            url: The URL to get robots.txt for

        Returns:
            The robots.txt URL
        """
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        return robots_url

    def _get_domain(self, url: str) -> str:
        """
        Extract domain from URL for caching.

        Args:
            url: The URL to extract domain from

        Returns:
            Domain string (scheme + netloc)
        """
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _fetch_robots_txt(self, robots_url: str) -> Optional[str]:
        """
        Fetch robots.txt content from URL.

        Args:
            robots_url: The robots.txt URL to fetch

        Returns:
            robots.txt content as string, or None if not found/error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    logger.debug(f"No robots.txt found at {robots_url}, allowing by default")
                    return None
                else:
                    logger.warning(
                        f"Unexpected status {response.status_code} fetching {robots_url}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching robots.txt from {robots_url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching robots.txt from {robots_url}: {e}")
            return None

    async def _get_parser(self, url: str) -> Optional[RobotFileParser]:
        """
        Get RobotFileParser for a URL, using cache if available.

        Args:
            url: The URL to get parser for

        Returns:
            RobotFileParser if robots.txt exists, None otherwise
        """
        domain = self._get_domain(url)

        # Check cache first
        cached_parser = self._cache.get(domain)
        if cached_parser is not None:
            return cached_parser

        # Fetch and parse robots.txt
        robots_url = self._get_robots_url(url)
        robots_content = await self._fetch_robots_txt(robots_url)

        if robots_content is None:
            # No robots.txt found, cache a permissive parser
            parser = RobotFileParser()
            parser.parse([])  # Empty robots.txt = allow everything
            self._cache.set(domain, parser)
            return None  # Signal that there's no robots.txt

        # Parse robots.txt
        parser = RobotFileParser()
        parser.parse(robots_content.splitlines())
        self._cache.set(domain, parser)
        return parser

    async def is_allowed(
        self,
        url: str,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        Check if a URL is allowed to be scraped according to robots.txt.

        Args:
            url: The URL to check
            user_agent: Optional user agent override

        Returns:
            True if scraping is allowed, False otherwise
        """
        try:
            parser = await self._get_parser(url)

            # If no robots.txt exists, allow by default
            if parser is None:
                return True

            # Check if URL is allowed for our user agent
            agent = user_agent or self.user_agent
            return parser.can_fetch(agent, url)

        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            # On error, be conservative and allow (fail open)
            return True

    async def get_crawl_delay(
        self,
        url: str,
        user_agent: Optional[str] = None,
    ) -> Optional[float]:
        """
        Get the crawl delay specified in robots.txt for a URL.

        Args:
            url: The URL to check
            user_agent: Optional user agent override

        Returns:
            Crawl delay in seconds, or None if not specified
        """
        try:
            parser = await self._get_parser(url)

            if parser is None:
                return None

            agent = user_agent or self.user_agent
            delay = parser.crawl_delay(agent)

            return float(delay) if delay is not None else None

        except Exception as e:
            logger.error(f"Error getting crawl delay for {url}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()

    def remove_from_cache(self, url: str) -> None:
        """
        Remove a specific domain from the cache.

        Args:
            url: Any URL from the domain to remove
        """
        domain = self._get_domain(url)
        self._cache.remove(domain)


# Global instance for shared use
_default_checker: Optional[RobotsChecker] = None


def get_robots_checker() -> RobotsChecker:
    """
    Get the default global RobotsChecker instance.

    Returns:
        The default RobotsChecker instance
    """
    global _default_checker
    if _default_checker is None:
        _default_checker = RobotsChecker()
    return _default_checker
