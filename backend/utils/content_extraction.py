"""Content extraction utilities for web scraping."""
import re
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


def clean_html(html: str) -> str:
    """
    Clean HTML by removing scripts, styles, and other non-content elements.

    Args:
        html: Raw HTML content

    Returns:
        Cleaned HTML with non-content elements removed
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        # Remove script and style elements
        for element in soup(["script", "style", "noscript", "iframe"]):
            element.decompose()

        # Remove common non-content elements
        for element in soup.find_all(
            ["nav", "header", "footer", "aside"],
            class_=lambda c: c and any(
                keyword in str(c).lower()
                for keyword in ["nav", "menu", "sidebar", "footer", "header", "cookie", "banner"]
            ),
        ):
            element.decompose()

        # Remove elements with common non-content classes
        for element in soup.find_all(
            class_=lambda c: c and any(
                keyword in str(c).lower()
                for keyword in [
                    "advertisement",
                    "ad-",
                    "social-share",
                    "comment",
                    "cookie-notice",
                    "popup",
                    "modal",
                ]
            )
        ):
            element.decompose()

        return str(soup)

    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        return html


def extract_text(html: str, clean_first: bool = True) -> str:
    """
    Extract clean text content from HTML.

    Args:
        html: HTML content
        clean_first: Whether to clean HTML before extracting text

    Returns:
        Extracted text content
    """
    try:
        if clean_first:
            html = clean_html(html)

        soup = BeautifulSoup(html, "lxml")

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)  # Remove excessive blank lines
        text = re.sub(r" +", " ", text)  # Remove excessive spaces
        text = text.strip()

        return text

    except Exception as e:
        logger.error(f"Error extracting text from HTML: {e}")
        return ""


def extract_title(html: str) -> Optional[str]:
    """
    Extract page title from HTML.

    Tries multiple methods:
    1. <title> tag
    2. <h1> tag
    3. og:title meta tag
    4. twitter:title meta tag

    Args:
        html: HTML content

    Returns:
        Page title or None if not found
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        # Try <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # Try og:title meta tag
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try twitter:title meta tag
        twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
        if twitter_title and twitter_title.get("content"):
            return twitter_title["content"].strip()

        # Try first <h1> tag
        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.string:
            return h1_tag.string.strip()

        return None

    except Exception as e:
        logger.error(f"Error extracting title from HTML: {e}")
        return None


def extract_meta_description(html: str) -> Optional[str]:
    """
    Extract meta description from HTML.

    Tries multiple methods:
    1. Standard meta description
    2. og:description
    3. twitter:description

    Args:
        html: HTML content

    Returns:
        Meta description or None if not found
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        # Try standard meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()

        # Try og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"].strip()

        # Try twitter:description
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        if twitter_desc and twitter_desc.get("content"):
            return twitter_desc["content"].strip()

        return None

    except Exception as e:
        logger.error(f"Error extracting meta description from HTML: {e}")
        return None


def extract_links(html: str, base_url: str) -> list[str]:
    """
    Extract all links from HTML and normalize them.

    Args:
        html: HTML content
        base_url: Base URL for resolving relative links

    Returns:
        List of absolute URLs
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # Skip non-HTTP(S) links
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Make absolute URL
            absolute_url = urljoin(base_url, href)

            # Parse and clean URL
            parsed = urlparse(absolute_url)

            # Skip if not HTTP(S)
            if parsed.scheme not in ["http", "https"]:
                continue

            # Reconstruct URL without fragment
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"

            # Add to list if not already present
            if clean_url not in links:
                links.append(clean_url)

        return links

    except Exception as e:
        logger.error(f"Error extracting links from HTML: {e}")
        return []


def detect_language(text: str) -> Optional[str]:
    """
    Detect the language of text content.

    Args:
        text: Text content to detect language for

    Returns:
        ISO 639-1 language code (e.g., 'en', 'es', 'fr') or None if detection fails
    """
    if not text or len(text.strip()) < 50:
        return None

    try:
        # Take first 10000 characters for better performance
        sample = text[:10000]
        lang = detect(sample)
        return lang

    except LangDetectException:
        logger.debug("Could not detect language")
        return None
    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        return None


def count_words(text: str) -> int:
    """
    Count words in text content.

    Args:
        text: Text content

    Returns:
        Word count
    """
    if not text:
        return 0

    # Split by whitespace and count
    words = text.split()
    return len(words)


def get_text_statistics(text: str) -> dict:
    """
    Get statistics about text content.

    Args:
        text: Text content

    Returns:
        Dictionary with text statistics
    """
    if not text:
        return {
            "word_count": 0,
            "character_count": 0,
            "line_count": 0,
        }

    return {
        "word_count": count_words(text),
        "character_count": len(text),
        "line_count": len(text.splitlines()),
    }


def extract_structured_data(html: str) -> dict:
    """
    Extract structured data (JSON-LD, microdata, RDFa) from HTML.

    Args:
        html: HTML content

    Returns:
        Dictionary with extracted structured data
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        structured_data = {}

        # Extract JSON-LD
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        if json_ld_scripts:
            import json

            json_ld_data = []
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    json_ld_data.append(data)
                except (json.JSONDecodeError, AttributeError):
                    continue

            if json_ld_data:
                structured_data["json_ld"] = json_ld_data

        # Extract Open Graph tags
        og_tags = {}
        for meta in soup.find_all("meta", property=lambda p: p and p.startswith("og:")):
            property_name = meta.get("property", "")
            content = meta.get("content", "")
            if property_name and content:
                og_tags[property_name] = content

        if og_tags:
            structured_data["open_graph"] = og_tags

        # Extract Twitter Card tags
        twitter_tags = {}
        for meta in soup.find_all("meta", attrs={"name": lambda n: n and n.startswith("twitter:")}):
            name = meta.get("name", "")
            content = meta.get("content", "")
            if name and content:
                twitter_tags[name] = content

        if twitter_tags:
            structured_data["twitter_card"] = twitter_tags

        return structured_data

    except Exception as e:
        logger.error(f"Error extracting structured data: {e}")
        return {}


def is_content_page(html: str, min_text_length: int = 500) -> bool:
    """
    Heuristic to determine if a page contains substantial content.

    Args:
        html: HTML content
        min_text_length: Minimum text length to consider a content page

    Returns:
        True if page appears to have substantial content
    """
    try:
        text = extract_text(html)

        # Check text length
        if len(text) < min_text_length:
            return False

        # Check for common content indicators
        soup = BeautifulSoup(html, "lxml")

        # Look for article or main content areas
        content_elements = soup.find_all(["article", "main"])
        if content_elements:
            return True

        # Look for paragraphs
        paragraphs = soup.find_all("p")
        if len(paragraphs) >= 3:
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking if content page: {e}")
        return True  # Err on the side of considering it content


def filter_same_domain(links: list[str], base_domain: str) -> list[str]:
    """
    Filter links to only include those from the same domain.

    Args:
        links: List of URLs
        base_domain: Base domain to filter by

    Returns:
        Filtered list of URLs from the same domain
    """
    filtered = []
    base_netloc = urlparse(base_domain).netloc.lower()

    for link in links:
        link_netloc = urlparse(link).netloc.lower()
        if link_netloc == base_netloc:
            filtered.append(link)

    return filtered


def filter_by_tlds(links: list[str], allowed_tlds: list[str]) -> list[str]:
    """
    Filter links to only include those with allowed TLDs.

    Args:
        links: List of URLs
        allowed_tlds: List of allowed TLDs (e.g., ['.org', '.edu'])

    Returns:
        Filtered list of URLs with allowed TLDs
    """
    filtered = []

    for link in links:
        netloc = urlparse(link).netloc.lower()
        if any(netloc.endswith(tld.lower()) for tld in allowed_tlds):
            filtered.append(link)

    return filtered
