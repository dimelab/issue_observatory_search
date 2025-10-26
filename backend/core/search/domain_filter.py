"""Domain filtering and sphere classification."""
import re
import logging
from typing import List, Optional, Set, Dict
from urllib.parse import urlparse
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Known domain lists by sphere
ACADEMIC_DOMAINS = {
    ".edu", ".ac.uk", ".edu.au", ".ac.nz", ".ac.za",
    "arxiv.org", "scholar.google.com", "researchgate.net",
    "academia.edu", "jstor.org", "springer.com", "sciencedirect.com",
}

GOVERNMENT_DOMAINS = {
    ".gov", ".gov.uk", ".gov.au", ".gov.nz", ".gov.ca",
    ".eu", ".europa.eu", ".gouv.fr", ".gob.es", ".gov.ie",
    "un.org", "who.int", "europa.eu",
}

NEWS_DOMAINS = {
    "bbc.co.uk", "bbc.com", "cnn.com", "theguardian.com", "nytimes.com",
    "washingtonpost.com", "reuters.com", "apnews.com", "bloomberg.com",
    "ft.com", "wsj.com", "economist.com", "politico.com", "npr.org",
    "dr.dk", "tv2.dk", "jyllands-posten.dk", "politiken.dk", "berlingske.dk",
}

NGO_ACTIVIST_DOMAINS = {
    "greenpeace.org", "wwf.org", "oxfam.org", "amnesty.org",
    "hrw.org", "eff.org", "aclu.org", "350.org", "foe.org",
    "climatecentral.org", "climatenetwork.org",
}

INDUSTRY_CORPORATE_DOMAINS = {
    "bloomberg.com", "ft.com", "wsj.com", "forbes.com",
    "businessinsider.com", "fortune.com", "inc.com",
}

INTERNATIONAL_ORG_DOMAINS = {
    "un.org", "who.int", "worldbank.org", "imf.org",
    "oecd.org", "wto.org", "nato.int", "europa.eu",
}


@dataclass
class SphereClassification:
    """
    Represents sphere classification for a domain.

    Attributes:
        domain: Domain name
        sphere: Classified sphere (academia, government, news, etc.)
        confidence: Confidence score (0.0-1.0)
        method: Classification method used
    """

    domain: str
    sphere: str
    confidence: float
    method: str


class DomainFilter:
    """
    Domain filtering and sphere classification engine.

    Provides comprehensive domain filtering with:
    1. Whitelist/blacklist filtering
    2. TLD (top-level domain) filtering
    3. Sphere classification (academia, government, news, NGO, etc.)
    4. URL validation

    Classification heuristics:
    - TLD-based: .edu/.ac.uk = academia, .gov = government
    - Domain list matching: Known news sites, NGOs, etc.
    - Pattern matching: Research institutions, international orgs
    """

    def __init__(
        self,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        tlds: Optional[List[str]] = None,
        spheres: Optional[List[str]] = None,
    ):
        """
        Initialize domain filter.

        Args:
            whitelist: List of allowed domains (exact or pattern)
            blacklist: List of blocked domains
            tlds: List of allowed TLDs (e.g., ['.dk', '.com'])
            spheres: List of allowed spheres
        """
        self.whitelist = set(whitelist) if whitelist else None
        self.blacklist = set(blacklist) if blacklist else set()
        self.tlds = set(tlds) if tlds else None
        self.spheres = set(spheres) if spheres else None

    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """
        Apply filters to search results.

        Args:
            results: List of result dicts with 'url' and 'domain' fields

        Returns:
            Filtered list of results
        """
        filtered = []

        for result in results:
            url = result.get("url", "")
            domain = result.get("domain", "")

            if not url or not domain:
                continue

            # Apply filters
            if not self.validate_url(url):
                logger.debug(f"Invalid URL: {url}")
                continue

            if self._is_blacklisted(domain):
                logger.debug(f"Blacklisted domain: {domain}")
                continue

            if self.whitelist and not self._is_whitelisted(domain):
                logger.debug(f"Not whitelisted: {domain}")
                continue

            if self.tlds and not self._matches_tld(domain):
                logger.debug(f"TLD mismatch: {domain}")
                continue

            if self.spheres:
                classification = self.classify_sphere(url)
                if classification.sphere not in self.spheres:
                    logger.debug(f"Sphere mismatch: {domain} ({classification.sphere})")
                    continue

            filtered.append(result)

        logger.info(f"Filtered {len(results)} results to {len(filtered)}")
        return filtered

    def classify_sphere(self, url: str) -> SphereClassification:
        """
        Classify domain into sphere.

        Uses multiple heuristics:
        1. TLD-based classification
        2. Known domain lists
        3. Pattern matching

        Args:
            url: URL to classify

        Returns:
            SphereClassification object
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove 'www.' prefix
            if domain.startswith("www."):
                domain = domain[4:]

            # Check TLD-based classification
            for tld in [".edu", ".ac.uk", ".ac.nz", ".ac.au"]:
                if domain.endswith(tld):
                    return SphereClassification(
                        domain=domain,
                        sphere="academia",
                        confidence=0.95,
                        method="tld",
                    )

            for tld in [".gov", ".gov.uk", ".gov.au", ".gov.nz"]:
                if domain.endswith(tld):
                    return SphereClassification(
                        domain=domain,
                        sphere="government",
                        confidence=0.95,
                        method="tld",
                    )

            # Check against known domain lists
            if self._domain_in_set(domain, ACADEMIC_DOMAINS):
                return SphereClassification(
                    domain=domain,
                    sphere="academia",
                    confidence=0.90,
                    method="domain_list",
                )

            if self._domain_in_set(domain, GOVERNMENT_DOMAINS):
                return SphereClassification(
                    domain=domain,
                    sphere="government",
                    confidence=0.90,
                    method="domain_list",
                )

            if self._domain_in_set(domain, NEWS_DOMAINS):
                return SphereClassification(
                    domain=domain,
                    sphere="news",
                    confidence=0.90,
                    method="domain_list",
                )

            if self._domain_in_set(domain, NGO_ACTIVIST_DOMAINS):
                return SphereClassification(
                    domain=domain,
                    sphere="activist",
                    confidence=0.85,
                    method="domain_list",
                )

            if self._domain_in_set(domain, INTERNATIONAL_ORG_DOMAINS):
                return SphereClassification(
                    domain=domain,
                    sphere="international",
                    confidence=0.90,
                    method="domain_list",
                )

            # Pattern-based classification
            if re.search(r'(university|college|institute|research)', domain, re.I):
                return SphereClassification(
                    domain=domain,
                    sphere="academia",
                    confidence=0.60,
                    method="pattern",
                )

            if re.search(r'(news|times|post|daily|tribune|herald)', domain, re.I):
                return SphereClassification(
                    domain=domain,
                    sphere="news",
                    confidence=0.50,
                    method="pattern",
                )

            if re.search(r'(ministry|parliament|senate|congress)', domain, re.I):
                return SphereClassification(
                    domain=domain,
                    sphere="government",
                    confidence=0.50,
                    method="pattern",
                )

            # Default to general
            return SphereClassification(
                domain=domain,
                sphere="general",
                confidence=0.30,
                method="default",
            )

        except Exception as e:
            logger.warning(f"Could not classify domain: {e}")
            return SphereClassification(
                domain="",
                sphere="unknown",
                confidence=0.0,
                method="error",
            )

    def validate_url(self, url: str) -> bool:
        """
        Validate URL format and accessibility.

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = urlparse(url)

            # Must have scheme (http/https)
            if parsed.scheme not in ["http", "https"]:
                return False

            # Must have netloc (domain)
            if not parsed.netloc:
                return False

            # Domain must have at least one dot
            if "." not in parsed.netloc:
                return False

            return True

        except Exception:
            return False

    def _is_blacklisted(self, domain: str) -> bool:
        """Check if domain is blacklisted."""
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        return domain in self.blacklist

    def _is_whitelisted(self, domain: str) -> bool:
        """Check if domain is whitelisted."""
        if not self.whitelist:
            return True

        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # Exact match
        if domain in self.whitelist:
            return True

        # Pattern match (e.g., '*.example.com')
        for pattern in self.whitelist:
            if pattern.startswith("*."):
                suffix = pattern[1:]  # Remove '*'
                if domain.endswith(suffix):
                    return True

        return False

    def _matches_tld(self, domain: str) -> bool:
        """Check if domain matches TLD filter."""
        if not self.tlds:
            return True

        domain = domain.lower()

        for tld in self.tlds:
            if domain.endswith(tld):
                return True

        return False

    def _domain_in_set(self, domain: str, domain_set: Set[str]) -> bool:
        """Check if domain is in a set of domains."""
        # Exact match
        if domain in domain_set:
            return True

        # TLD match
        for known_domain in domain_set:
            if known_domain.startswith("."):
                # It's a TLD
                if domain.endswith(known_domain):
                    return True
            else:
                # Check if it's a subdomain
                if domain.endswith("." + known_domain):
                    return True
                # Check exact match
                if domain == known_domain:
                    return True

        return False

    def get_sphere_distribution(self, results: List[Dict]) -> Dict[str, int]:
        """
        Get distribution of spheres in results.

        Args:
            results: List of result dicts with 'url' field

        Returns:
            Dict mapping sphere to count
        """
        distribution: Dict[str, int] = {}

        for result in results:
            url = result.get("url", "")
            if not url:
                continue

            classification = self.classify_sphere(url)
            sphere = classification.sphere

            distribution[sphere] = distribution.get(sphere, 0) + 1

        return distribution

    def get_available_spheres(self) -> List[str]:
        """
        Get list of available sphere classifications.

        Returns:
            List of sphere names
        """
        return [
            "academia",
            "government",
            "news",
            "activist",
            "industry",
            "international",
            "general",
            "unknown",
        ]
