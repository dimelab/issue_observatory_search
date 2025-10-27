"""Playwright-based web scraper with anti-bot handling and polite scraping."""
import asyncio
import logging
import random
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from backend.utils.robots import RobotsChecker
from backend.utils.content_extraction import (
    extract_text,
    extract_title,
    extract_meta_description,
    extract_links,
    detect_language,
    count_words,
)

logger = logging.getLogger(__name__)


class ScrapingResult:
    """
    Result of a scraping operation.

    Contains all extracted data and metadata from scraping a URL.
    """

    def __init__(
        self,
        url: str,
        status: str,
        html_content: Optional[str] = None,
        extracted_text: Optional[str] = None,
        title: Optional[str] = None,
        meta_description: Optional[str] = None,
        language: Optional[str] = None,
        word_count: int = 0,
        outbound_links: Optional[list[str]] = None,
        http_status_code: Optional[int] = None,
        final_url: Optional[str] = None,
        error_message: Optional[str] = None,
        duration: float = 0.0,
    ):
        """Initialize scraping result."""
        self.url = url
        self.status = status  # success, failed, skipped
        self.html_content = html_content
        self.extracted_text = extracted_text
        self.title = title
        self.meta_description = meta_description
        self.language = language
        self.word_count = word_count
        self.outbound_links = outbound_links or []
        self.http_status_code = http_status_code
        self.final_url = final_url or url
        self.error_message = error_message
        self.duration = duration

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "url": self.url,
            "status": self.status,
            "html_content": self.html_content,
            "extracted_text": self.extracted_text,
            "title": self.title,
            "meta_description": self.meta_description,
            "language": self.language,
            "word_count": self.word_count,
            "outbound_links": self.outbound_links,
            "http_status_code": self.http_status_code,
            "final_url": self.final_url,
            "error_message": self.error_message,
            "duration": self.duration,
        }


class PlaywrightScraper:
    """
    Playwright-based web scraper with anti-bot measures and polite scraping.

    Features:
    - JavaScript rendering with Playwright
    - Robots.txt checking
    - Random delays between requests
    - Exponential backoff retry logic
    - CAPTCHA detection
    - Rate limiting (429) handling
    - Proper timeout handling
    - User-agent rotation
    """

    def __init__(
        self,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_retries: int = 3,
        timeout: int = 30,
        respect_robots_txt: bool = True,
        user_agent: Optional[str] = None,
        headless: bool = True,
    ):
        """
        Initialize the Playwright scraper.

        Args:
            delay_min: Minimum delay between requests in seconds
            delay_max: Maximum delay between requests in seconds
            max_retries: Maximum number of retry attempts
            timeout: Page load timeout in seconds
            respect_robots_txt: Whether to check and respect robots.txt
            user_agent: Custom user agent string
            headless: Whether to run browser in headless mode
        """
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.timeout = timeout * 1000  # Convert to milliseconds for Playwright
        self.respect_robots_txt = respect_robots_txt
        self.headless = headless

        # Default user agent (recent Chrome on Windows - more common than Mac)
        # Updated to latest stable Chrome version for better compatibility
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # Initialize robots checker
        self.robots_checker = RobotsChecker(
            user_agent="IssueObservatoryBot/1.0",
            cache_ttl_minutes=60,
        ) if respect_robots_txt else None

        # Browser instance (reused across requests)
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def _ensure_browser(self) -> Browser:
        """
        Ensure browser is initialized with stealth settings.

        Returns:
            Browser instance
        """
        if self._browser is None:
            self._playwright = await async_playwright().start()

            # Launch arguments for maximum stealth
            launch_args = [
                # Core anti-detection
                "--disable-blink-features=AutomationControlled",

                # Memory and performance
                "--disable-dev-shm-usage",
                "--no-sandbox",

                # Browser behavior
                "--disable-infobars",
                "--disable-extensions",
                "--disable-setuid-sandbox",

                # Reduce fingerprinting
                "--window-size=1920,1080",
                "--start-maximized",

                # Disable automation flags
                "--disable-automation",
                "--disable-blink-features",
            ]

            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
                executable_path="/usr/bin/google-chrome",  # Use installed Chrome
            )
            logger.info(f"Browser launched: executable=/usr/bin/google-chrome, headless={self.headless}")
        return self._browser

    async def close(self) -> None:
        """Close browser and clean up resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _create_page(self) -> Page:
        """
        Create a new browser page with enhanced anti-detection measures.

        Returns:
            Configured Page instance
        """
        browser = await self._ensure_browser()
        context = await browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            # Additional stealth settings
            has_touch=False,
            java_script_enabled=True,
            ignore_https_errors=True,
            # Add realistic device scale factor
            device_scale_factor=1,
            # Add realistic screen size (desktop)
            screen={"width": 1920, "height": 1080},
            # Bypass CSP for better compatibility
            bypass_csp=True,
        )

        # Add realistic HTTP headers
        await context.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })

        page = await context.new_page()

        # Comprehensive anti-detection script
        await page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Override plugins to avoid headless detection
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Chrome specific properties
            window.chrome = {
                runtime: {}
            };

            // Permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Remove automation-specific properties
            delete navigator.__proto__.webdriver;
        """)

        return page

    async def _check_robots_txt(self, url: str) -> tuple[bool, Optional[float]]:
        """
        Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            Tuple of (is_allowed, crawl_delay)
        """
        if not self.robots_checker:
            return True, None

        try:
            is_allowed = await self.robots_checker.is_allowed(url)
            crawl_delay = await self.robots_checker.get_crawl_delay(url) if is_allowed else None
            return is_allowed, crawl_delay

        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            return True, None  # Fail open

    async def _polite_delay(self, crawl_delay: Optional[float] = None) -> None:
        """
        Wait for a polite delay between requests.

        Args:
            crawl_delay: Optional crawl delay from robots.txt
        """
        if crawl_delay:
            delay = max(crawl_delay, self.delay_min)
        else:
            delay = random.uniform(self.delay_min, self.delay_max)

        await asyncio.sleep(delay)

    def _is_captcha_page(self, html: str, url: str) -> bool:
        """
        Detect if page is a CAPTCHA challenge.

        Args:
            html: Page HTML content
            url: Page URL

        Returns:
            True if CAPTCHA detected
        """
        html_lower = html.lower()

        # Common CAPTCHA indicators
        captcha_indicators = [
            "recaptcha",
            "captcha",
            "cf-challenge",
            "cloudflare",
            "please verify you are a human",
            "are you a robot",
            "security check",
        ]

        return any(indicator in html_lower for indicator in captcha_indicators)

    def _is_rate_limited(self, status_code: Optional[int], html: str) -> bool:
        """
        Detect if we're being rate limited.

        Args:
            status_code: HTTP status code
            html: Page HTML content

        Returns:
            True if rate limited
        """
        if status_code == 429:
            return True

        html_lower = html.lower()
        rate_limit_indicators = [
            "too many requests",
            "rate limit",
            "slow down",
        ]

        return any(indicator in html_lower for indicator in rate_limit_indicators)

    async def _scrape_with_retry(
        self,
        url: str,
        retry_count: int = 0,
    ) -> ScrapingResult:
        """
        Scrape URL with retry logic.

        Args:
            url: URL to scrape
            retry_count: Current retry attempt number

        Returns:
            ScrapingResult
        """
        page = None
        start_time = datetime.utcnow()

        try:
            # Create new page
            page = await self._create_page()

            # Navigate to URL with realistic waiting
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout,
            )

            # Wait for dynamic content to load (2-3 seconds for more human-like behavior)
            await page.wait_for_timeout(random.randint(2000, 3000))

            # Get final URL (after redirects)
            final_url = page.url

            # Get HTML content
            html_content = await page.content()

            # Get HTTP status
            http_status_code = response.status if response else None

            # Check for CAPTCHA
            if self._is_captcha_page(html_content, final_url):
                logger.warning(f"CAPTCHA detected for {url}")
                return ScrapingResult(
                    url=url,
                    status="failed",
                    error_message="CAPTCHA challenge detected",
                    http_status_code=http_status_code,
                    final_url=final_url,
                    duration=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Check for rate limiting
            if self._is_rate_limited(http_status_code, html_content):
                logger.warning(f"Rate limiting detected for {url}")

                if retry_count < self.max_retries:
                    # Exponential backoff
                    backoff_delay = (2 ** retry_count) * self.delay_max
                    logger.info(f"Retrying {url} after {backoff_delay}s backoff (attempt {retry_count + 1})")
                    await asyncio.sleep(backoff_delay)
                    return await self._scrape_with_retry(url, retry_count + 1)

                return ScrapingResult(
                    url=url,
                    status="failed",
                    error_message="Rate limited after retries",
                    http_status_code=http_status_code,
                    final_url=final_url,
                    duration=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Extract content
            extracted_text = extract_text(html_content)
            title = extract_title(html_content)
            meta_description = extract_meta_description(html_content)
            outbound_links = extract_links(html_content, final_url)
            language = detect_language(extracted_text)
            word_count = count_words(extracted_text)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return ScrapingResult(
                url=url,
                status="success",
                html_content=html_content,
                extracted_text=extracted_text,
                title=title,
                meta_description=meta_description,
                language=language,
                word_count=word_count,
                outbound_links=outbound_links,
                http_status_code=http_status_code,
                final_url=final_url,
                duration=duration,
            )

        except PlaywrightTimeoutError:
            logger.warning(f"Timeout scraping {url}")

            if retry_count < self.max_retries:
                logger.info(f"Retrying {url} (attempt {retry_count + 1})")
                await asyncio.sleep(self.delay_max)
                return await self._scrape_with_retry(url, retry_count + 1)

            return ScrapingResult(
                url=url,
                status="failed",
                error_message="Timeout loading page",
                duration=(datetime.utcnow() - start_time).total_seconds(),
            )

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")

            if retry_count < self.max_retries:
                logger.info(f"Retrying {url} after error (attempt {retry_count + 1})")
                await asyncio.sleep(self.delay_max)
                return await self._scrape_with_retry(url, retry_count + 1)

            return ScrapingResult(
                url=url,
                status="failed",
                error_message=str(e),
                duration=(datetime.utcnow() - start_time).total_seconds(),
            )

        finally:
            if page:
                await page.close()

    async def scrape(self, url: str) -> ScrapingResult:
        """
        Scrape a single URL with robots.txt checking and polite delays.

        Args:
            url: URL to scrape

        Returns:
            ScrapingResult with extracted data
        """
        try:
            # Check robots.txt
            is_allowed, crawl_delay = await self._check_robots_txt(url)

            if not is_allowed:
                logger.info(f"URL {url} blocked by robots.txt")
                return ScrapingResult(
                    url=url,
                    status="skipped",
                    error_message="Blocked by robots.txt",
                )

            # Polite delay before scraping
            await self._polite_delay(crawl_delay)

            # Scrape with retry logic
            result = await self._scrape_with_retry(url)

            return result

        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return ScrapingResult(
                url=url,
                status="failed",
                error_message=f"Unexpected error: {str(e)}",
            )

    async def scrape_multiple(
        self,
        urls: list[str],
        concurrency: int = 1,
    ) -> list[ScrapingResult]:
        """
        Scrape multiple URLs with controlled concurrency.

        Args:
            urls: List of URLs to scrape
            concurrency: Number of concurrent scraping operations

        Returns:
            List of ScrapingResults
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def scrape_with_semaphore(url: str) -> ScrapingResult:
            async with semaphore:
                return await self.scrape(url)

        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    ScrapingResult(
                        url=urls[i],
                        status="failed",
                        error_message=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
