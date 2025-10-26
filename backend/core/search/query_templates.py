"""Query template manager for formulation strategies."""
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Built-in framings for English
FRAMINGS_EN = {
    "neutral": [
        "{issue}",
        "{issue} information",
        "{issue} overview",
    ],
    "activist": [
        "{issue} crisis",
        "{issue} emergency",
        "{issue} action",
        "solve {issue}",
        "fight {issue}",
    ],
    "skeptic": [
        "{issue} skepticism",
        "{issue} debate",
        "{issue} controversy",
        "{issue} doubt",
        "question {issue}",
    ],
    "scientific": [
        "{issue} research",
        "{issue} science",
        "{issue} study",
        "{issue} evidence",
        "{issue} peer review",
    ],
    "policy": [
        "{issue} policy",
        "{issue} regulation",
        "{issue} legislation",
        "{issue} government",
        "{issue} law",
    ],
    "industry": [
        "{issue} business",
        "{issue} market",
        "{issue} economy",
        "{issue} investment",
        "{issue} corporate",
    ],
    "media": [
        "{issue} news",
        "{issue} coverage",
        "{issue} media",
        "{issue} report",
    ],
    "local": [
        "{issue} in {location}",
        "{location} {issue}",
        "{issue} {location} impact",
    ],
    "temporal": [
        "{issue} {year}",
        "{issue} history",
        "{issue} timeline",
        "future of {issue}",
    ],
}

# Built-in framings for Danish
FRAMINGS_DA = {
    "neutral": [
        "{issue}",
        "{issue} information",
        "{issue} oversigt",
    ],
    "activist": [
        "{issue}krise",
        "{issue}nødsituation",
        "{issue} handling",
        "bekæmp {issue}",
        "løs {issue}",
    ],
    "skeptic": [
        "{issue} skepsis",
        "{issue} debat",
        "{issue} kontrovers",
        "tvivl om {issue}",
    ],
    "scientific": [
        "{issue} forskning",
        "{issue} videnskab",
        "{issue} undersøgelse",
        "{issue} evidens",
    ],
    "policy": [
        "{issue} politik",
        "{issue} regulering",
        "{issue} lovgivning",
        "{issue} regering",
    ],
    "industry": [
        "{issue} erhverv",
        "{issue} marked",
        "{issue} økonomi",
        "{issue} investering",
    ],
    "media": [
        "{issue} nyheder",
        "{issue} dækning",
        "{issue} medie",
    ],
    "local": [
        "{issue} i {location}",
        "{location} {issue}",
        "{issue} {location} påvirkning",
    ],
    "temporal": [
        "{issue} {year}",
        "{issue} historie",
        "{issue} tidslinje",
        "fremtid for {issue}",
    ],
}

# Mapping of languages to framings
LANGUAGE_FRAMINGS = {
    "en": FRAMINGS_EN,
    "da": FRAMINGS_DA,
}


@dataclass
class QueryTemplate:
    """
    Represents a query template.

    Attributes:
        template: Template string with variables (e.g., "{issue} in {location}")
        variables: List of variable names in the template
        framing_type: Type of framing (neutral, activist, etc.)
        language: Language code
    """

    template: str
    variables: List[str]
    framing_type: str
    language: str


class QueryTemplateManager:
    """
    Manages query templates and formulation strategies.

    Provides built-in framings for multiple languages and supports
    custom user-defined templates. Enables multi-perspective
    searching by generating queries with different framings.
    """

    def __init__(self):
        """Initialize query template manager."""
        self.custom_templates: Dict[int, QueryTemplate] = {}

    def get_framings(
        self,
        language: str = "en",
        issue: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        Get available framings for a language.

        Args:
            language: Language code (en, da)
            issue: Optional issue to substitute in templates

        Returns:
            Dict mapping framing types to query lists
        """
        framings = LANGUAGE_FRAMINGS.get(language, FRAMINGS_EN)

        if issue:
            # Substitute issue in templates
            result = {}
            for framing_type, templates in framings.items():
                result[framing_type] = [
                    t.format(issue=issue) if "{issue}" in t else t
                    for t in templates
                ]
            return result

        return framings.copy()

    def apply_framing(
        self,
        framing_type: str,
        language: str = "en",
        substitutions: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        Generate queries for a specific framing.

        Args:
            framing_type: Type of framing (neutral, activist, etc.)
            language: Language code
            substitutions: Dict of variable substitutions

        Returns:
            List of generated queries

        Raises:
            ValueError: If framing_type not found
        """
        framings = LANGUAGE_FRAMINGS.get(language, FRAMINGS_EN)

        if framing_type not in framings:
            available = list(framings.keys())
            raise ValueError(
                f"Framing '{framing_type}' not found. Available: {', '.join(available)}"
            )

        templates = framings[framing_type]

        if not substitutions:
            return templates

        # Apply substitutions
        queries = []
        for template in templates:
            try:
                query = template.format(**substitutions)
                queries.append(query)
            except KeyError as e:
                logger.warning(
                    f"Missing variable {e} for template '{template}'. Skipping."
                )
                continue

        return queries

    def generate_multi_perspective_queries(
        self,
        issue: str,
        language: str = "en",
        framings: Optional[List[str]] = None,
        location: Optional[str] = None,
        year: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        Generate queries for multiple framings.

        Creates a comprehensive set of queries representing different
        perspectives on an issue.

        Args:
            issue: Main issue/topic
            language: Language code
            framings: List of framing types to include (all if None)
            location: Optional location for local framing
            year: Optional year for temporal framing

        Returns:
            Dict mapping framing types to query lists
        """
        logger.info(f"Generating multi-perspective queries for '{issue}' in {language}")

        available_framings = LANGUAGE_FRAMINGS.get(language, FRAMINGS_EN)

        if framings is None:
            framings = list(available_framings.keys())

        # Build substitutions
        substitutions = {"issue": issue}
        if location:
            substitutions["location"] = location
        if year:
            substitutions["year"] = year

        # Generate queries for each framing
        result = {}
        for framing_type in framings:
            if framing_type in available_framings:
                queries = self.apply_framing(
                    framing_type=framing_type,
                    language=language,
                    substitutions=substitutions,
                )
                result[framing_type] = queries

        total_queries = sum(len(queries) for queries in result.values())
        logger.info(
            f"Generated {total_queries} queries across {len(result)} framings"
        )

        return result

    def create_custom_template(
        self,
        template: str,
        framing_type: str,
        language: str = "en",
        template_id: Optional[int] = None,
    ) -> QueryTemplate:
        """
        Create a custom query template.

        Args:
            template: Template string with {variable} placeholders
            framing_type: Type of framing
            language: Language code
            template_id: Optional ID for storing

        Returns:
            QueryTemplate object
        """
        # Extract variables from template
        variables = self._extract_variables(template)

        query_template = QueryTemplate(
            template=template,
            variables=variables,
            framing_type=framing_type,
            language=language,
        )

        if template_id is not None:
            self.custom_templates[template_id] = query_template

        logger.info(
            f"Created custom template with variables: {', '.join(variables)}"
        )

        return query_template

    def apply_custom_template(
        self,
        template: QueryTemplate,
        substitutions: Dict[str, str],
    ) -> str:
        """
        Apply substitutions to a custom template.

        Args:
            template: QueryTemplate object
            substitutions: Dict of variable substitutions

        Returns:
            Generated query string

        Raises:
            ValueError: If required variables missing
        """
        # Check for missing variables
        missing = set(template.variables) - set(substitutions.keys())
        if missing:
            raise ValueError(
                f"Missing required variables: {', '.join(missing)}"
            )

        # Apply substitutions
        query = template.template.format(**substitutions)
        return query

    def translate_framing(
        self,
        queries: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:
        """
        Translate framings between languages.

        Note: This is a simple mapping-based translation. For production,
        consider using a proper translation API.

        Args:
            queries: List of queries to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translated queries
        """
        # Simple mapping for common issue terms
        issue_translations = {
            ("en", "da"): {
                "climate change": "klimaændringer",
                "global warming": "global opvarmning",
                "climate crisis": "klimakrise",
                "climate emergency": "klimanødsituation",
                "climate policy": "klimapolitik",
                "climate science": "klimavidenskab",
            },
            ("da", "en"): {
                "klimaændringer": "climate change",
                "global opvarmning": "global warming",
                "klimakrise": "climate crisis",
                "klimanødsituation": "climate emergency",
                "klimapolitik": "climate policy",
                "klimavidenskab": "climate science",
            },
        }

        translation_map = issue_translations.get((source_lang, target_lang), {})

        if not translation_map:
            logger.warning(
                f"No translation map available for {source_lang} -> {target_lang}"
            )
            return queries

        translated = []
        for query in queries:
            translated_query = query
            for source_term, target_term in translation_map.items():
                translated_query = translated_query.replace(source_term, target_term)
            translated.append(translated_query)

        return translated

    def get_template_variables(self, template_str: str) -> List[str]:
        """
        Extract variable names from a template string.

        Args:
            template_str: Template string

        Returns:
            List of variable names
        """
        return self._extract_variables(template_str)

    def _extract_variables(self, template: str) -> List[str]:
        """
        Extract variable names from template string.

        Args:
            template: Template string with {variable} placeholders

        Returns:
            List of unique variable names
        """
        pattern = r'\{(\w+)\}'
        variables = re.findall(pattern, template)
        return list(set(variables))

    def validate_template(
        self,
        template: str,
        substitutions: Dict[str, str],
    ) -> bool:
        """
        Validate that a template can be applied with given substitutions.

        Args:
            template: Template string
            substitutions: Dict of substitutions

        Returns:
            True if valid, False otherwise
        """
        variables = self._extract_variables(template)
        return all(var in substitutions for var in variables)
