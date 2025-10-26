"""
WebsiteContentFactory - Generate realistic synthetic website content.

This factory generates structured website content that mimics real websites:
- Different content types (news, academic, blog, government report)
- Realistic HTML structure and text extraction
- Issue-specific vocabulary and terminology
- Realistic word counts and noun density
- Linked pages for depth testing
- Edge cases (empty, very long, malformed)
"""
from typing import Dict, List, Optional, Any
import random
from faker import Faker
from urllib.parse import urlparse, urljoin

from .base import (
    set_seed,
    get_issue_vocabulary,
    detect_language,
    generate_zipf_frequencies
)


class WebsiteContentFactory:
    """Generate synthetic website content for different domains."""

    # Content type templates with realistic parameters
    CONTENT_TEMPLATES = {
        'news_article': {
            'structure': ['headline', 'byline', 'lead', 'body_paragraphs', 'quotes'],
            'avg_length': 800,
            'paragraph_count': 8,
            'noun_density': 0.15,
            'has_images': True
        },
        'academic_paper': {
            'structure': ['title', 'abstract', 'introduction', 'methodology', 'results', 'conclusion', 'references'],
            'avg_length': 3000,
            'paragraph_count': 20,
            'noun_density': 0.20,
            'has_images': True
        },
        'blog_post': {
            'structure': ['title', 'intro', 'sections', 'conclusion', 'comments'],
            'avg_length': 1200,
            'paragraph_count': 10,
            'noun_density': 0.12,
            'has_images': True
        },
        'government_report': {
            'structure': ['title', 'executive_summary', 'sections', 'recommendations', 'appendix'],
            'avg_length': 2000,
            'paragraph_count': 15,
            'noun_density': 0.18,
            'has_images': False
        },
        'landing_page': {
            'structure': ['hero', 'features', 'cta'],
            'avg_length': 400,
            'paragraph_count': 5,
            'noun_density': 0.10,
            'has_images': True
        }
    }

    @classmethod
    def create_website_content(
        cls,
        url: str,
        issue_type: str,
        depth: int = 1,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate synthetic website content with realistic structure.

        Args:
            url: Website URL
            issue_type: Type of issue (determines vocabulary)
            depth: Number of linked page levels to generate (1 = main page only)
            seed: Random seed for reproducibility

        Returns:
            Dictionary with keys:
                - url: Original URL
                - html: Full HTML content
                - text: Extracted plain text
                - linked_pages: List of linked page dictionaries (if depth > 1)
                - metadata: Dict with title, language, word_count, scraped_at

        Example:
            >>> content = WebsiteContentFactory.create_website_content(
            ...     'https://example.com/article',
            ...     'climate',
            ...     depth=2,
            ...     seed=42
            ... )
            >>> assert 'html' in content
            >>> assert 'text' in content
            >>> assert len(content['linked_pages']) > 0
        """
        if seed is not None:
            set_seed(seed)

        fake = Faker()
        if seed is not None:
            Faker.seed(seed)

        # Determine content type from URL
        content_type = cls._determine_content_type(url)
        template = cls.CONTENT_TEMPLATES[content_type]

        # Generate main content
        content_data = cls._generate_structured_content(
            template, issue_type, fake, seed
        )

        # Generate linked pages for depth > 1
        linked_pages = []
        if depth > 1:
            num_links = random.randint(3, 10)
            for i in range(num_links):
                linked_url = cls._generate_related_url(url, i)
                # Generate simpler content for linked pages (depth 1)
                linked_content_data = cls._generate_structured_content(
                    template, issue_type, fake, seed + i if seed else None
                )
                linked_pages.append({
                    'url': linked_url,
                    'html': cls._wrap_in_html(linked_content_data, linked_url),
                    'text': cls._extract_text(linked_content_data),
                    'metadata': {
                        'title': linked_content_data.get('title', ''),
                        'language': detect_language(linked_content_data.get('text', '')),
                        'word_count': len(linked_content_data.get('text', '').split()),
                    }
                })

        # Detect language from URL or content
        language = cls._detect_language_from_url(url)

        return {
            'url': url,
            'html': cls._wrap_in_html(content_data, url),
            'text': cls._extract_text(content_data),
            'linked_pages': linked_pages,
            'metadata': {
                'title': content_data.get('title', ''),
                'language': language,
                'word_count': len(content_data.get('text', '').split()),
                'content_type': content_type
            }
        }

    @classmethod
    def create_bulk_content(
        cls,
        urls: List[str],
        issue_type: str,
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate content for multiple URLs efficiently.

        Args:
            urls: List of URLs to generate content for
            issue_type: Type of issue
            seed: Random seed for reproducibility

        Returns:
            List of content dictionaries

        Example:
            >>> urls = [f'https://example{i}.com/page' for i in range(5)]
            >>> contents = WebsiteContentFactory.create_bulk_content(urls, 'climate')
            >>> assert len(contents) == 5
        """
        if seed is not None:
            set_seed(seed)

        contents = []
        for i, url in enumerate(urls):
            url_seed = seed + i if seed is not None else None
            contents.append(
                cls.create_website_content(url, issue_type, depth=1, seed=url_seed)
            )

        return contents

    @classmethod
    def create_edge_case_content(
        cls,
        case_type: str,
        url: str = 'https://example.com/edge',
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate edge case content for testing robustness.

        Args:
            case_type: Type of edge case ('empty', 'huge', 'unicode', 'malformed')
            url: URL for the content
            seed: Random seed

        Returns:
            Content dictionary with edge case characteristics

        Example:
            >>> empty = WebsiteContentFactory.create_edge_case_content('empty')
            >>> assert empty['text'] == ''
            >>> huge = WebsiteContentFactory.create_edge_case_content('huge')
            >>> assert len(huge['text'].split()) > 50000
        """
        if seed is not None:
            set_seed(seed)

        fake = Faker()
        if seed is not None:
            Faker.seed(seed)

        if case_type == 'empty':
            return {
                'url': url,
                'html': '<html><body></body></html>',
                'text': '',
                'linked_pages': [],
                'metadata': {
                    'title': '',
                    'language': 'en',
                    'word_count': 0,
                    'content_type': 'empty'
                }
            }

        elif case_type == 'huge':
            # Generate very long content (50,000+ words)
            paragraphs = [fake.paragraph(nb_sentences=10) for _ in range(5000)]
            text = '\n\n'.join(paragraphs)
            html = f"<html><body><article>{''.join(f'<p>{p}</p>' for p in paragraphs)}</article></body></html>"

            return {
                'url': url,
                'html': html,
                'text': text,
                'linked_pages': [],
                'metadata': {
                    'title': 'Extremely Long Document',
                    'language': 'en',
                    'word_count': len(text.split()),
                    'content_type': 'huge'
                }
            }

        elif case_type == 'unicode':
            # Generate content with special Unicode characters
            unicode_text = (
                "Unicode test: 日本語 中文 한국어 العربية עברית Ελληνικά Русский\n"
                "Emojis: 🌍 🌡️ ⚡ 💨 ☀️ 🌊 🌳 🔬 📊 💡\n"
                "Math symbols: ∑ ∫ √ ∞ ≈ ≠ ≤ ≥ ± °\n"
                "Special chars: © ® ™ § ¶ † ‡ • ‰ €\n"
                + fake.text(max_nb_chars=500)
            )
            html = f"<html><head><meta charset='utf-8'></head><body><p>{unicode_text}</p></body></html>"

            return {
                'url': url,
                'html': html,
                'text': unicode_text,
                'linked_pages': [],
                'metadata': {
                    'title': 'Unicode Content Test',
                    'language': 'en',
                    'word_count': len(unicode_text.split()),
                    'content_type': 'unicode'
                }
            }

        elif case_type == 'malformed':
            # Generate malformed HTML
            html = """
            <html>
            <body>
            <div>Unclosed div
            <p>Paragraph without closing
            <span>Nested unclosed <b>tags
            <script>alert('test')</script>
            </html>
            """
            text = "Unclosed div Paragraph without closing Nested unclosed tags"

            return {
                'url': url,
                'html': html,
                'text': text,
                'linked_pages': [],
                'metadata': {
                    'title': 'Malformed HTML',
                    'language': 'en',
                    'word_count': len(text.split()),
                    'content_type': 'malformed'
                }
            }

        else:
            raise ValueError(f"Unknown edge case type: {case_type}")

    @classmethod
    def _determine_content_type(cls, url: str) -> str:
        """
        Determine content type from URL patterns.

        Args:
            url: Website URL

        Returns:
            Content type string
        """
        url_lower = url.lower()

        if any(pattern in url_lower for pattern in ['/news/', '/article/', 'newsroom']):
            return 'news_article'
        elif any(pattern in url_lower for pattern in ['/paper/', '/research/', '/journal/', 'academic']):
            return 'academic_paper'
        elif any(pattern in url_lower for pattern in ['/blog/', '/post/', 'medium.com', 'substack']):
            return 'blog_post'
        elif any(pattern in url_lower for pattern in ['.gov', '/report/', '/policy/', 'europa.eu']):
            return 'government_report'
        else:
            return 'landing_page'

    @classmethod
    def _generate_structured_content(
        cls,
        template: Dict[str, Any],
        issue_type: str,
        fake: Faker,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate content following template structure.

        Args:
            template: Content template dictionary
            issue_type: Type of issue
            fake: Faker instance
            seed: Random seed

        Returns:
            Dictionary with content sections
        """
        if seed is not None:
            set_seed(seed)

        # Get relevant vocabulary for the issue
        vocab = get_issue_vocabulary(issue_type)

        content_parts = []
        title = ""

        for section in template['structure']:
            if section in ['headline', 'title', 'hero']:
                text = cls._generate_headline(vocab, fake)
                title = text
            elif section == 'abstract':
                text = cls._generate_abstract(vocab, fake, 150)
            elif section == 'byline':
                text = f"By {fake.name()} | {fake.date_time_between(start_date='-30d').strftime('%B %d, %Y')}"
            elif section == 'lead':
                text = cls._generate_lead_paragraph(vocab, fake)
            elif section in ['body_paragraphs', 'sections', 'introduction', 'methodology', 'results']:
                text = cls._generate_paragraphs(
                    vocab, fake, template['paragraph_count'] // 3, template['noun_density']
                )
            elif section == 'quotes':
                text = cls._generate_quotes(vocab, fake, 3)
            elif section == 'conclusion':
                text = cls._generate_conclusion(vocab, fake)
            elif section == 'references':
                text = cls._generate_references(fake, 10)
            elif section == 'executive_summary':
                text = cls._generate_abstract(vocab, fake, 200)
            elif section == 'recommendations':
                text = cls._generate_recommendations(vocab, fake, 5)
            elif section == 'features':
                text = cls._generate_features(vocab, fake, 3)
            elif section == 'cta':
                text = cls._generate_cta(vocab, fake)
            else:
                text = cls._generate_generic_section(vocab, fake, 100)

            content_parts.append({'section': section, 'text': text})

        return {
            'title': title,
            'sections': content_parts,
            'text': '\n\n'.join([part['text'] for part in content_parts])
        }

    @classmethod
    def _generate_headline(cls, vocab: Dict[str, List[str]], fake: Faker) -> str:
        """Generate realistic headline."""
        templates = [
            "New {keyword} breakthrough could transform {keyword2}",
            "How {entity} is leading {keyword} innovation",
            "The impact of {keyword} on global {keyword2}",
            "{keyword}: Challenges and opportunities ahead",
            "Understanding the role of {keyword} in {keyword2}",
            "{entity} announces major {keyword} initiative",
        ]

        template = random.choice(templates)
        return template.format(
            keyword=random.choice(vocab['keywords']),
            keyword2=random.choice(vocab['keywords']),
            entity=random.choice(vocab['entities'])
        )

    @classmethod
    def _generate_abstract(cls, vocab: Dict[str, List[str]], fake: Faker, word_count: int) -> str:
        """Generate academic-style abstract."""
        sentences = []

        # Purpose sentence
        sentences.append(
            f"This study examines the relationship between {random.choice(vocab['keywords'])} "
            f"and {random.choice(vocab['keywords'])} in contemporary contexts."
        )

        # Methods sentence
        sentences.append(
            f"Using {random.choice(vocab['adjectives'])} approaches, we analyze "
            f"{random.choice(vocab['keywords'])} across multiple dimensions."
        )

        # Results sentence
        sentences.append(
            f"Our findings reveal significant {random.choice(vocab['adjectives'])} patterns "
            f"in {random.choice(vocab['keywords'])} that have implications for policy and practice."
        )

        # Conclusion sentence
        sentences.append(
            f"These results contribute to our understanding of {random.choice(vocab['keywords'])} "
            f"and suggest pathways for future {random.choice(vocab['verbs'])} efforts."
        )

        return ' '.join(sentences)

    @classmethod
    def _generate_lead_paragraph(cls, vocab: Dict[str, List[str]], fake: Faker) -> str:
        """Generate news article lead paragraph."""
        return (
            f"{random.choice(vocab['entities'])} announced today a major initiative to "
            f"{random.choice(vocab['verbs'])} {random.choice(vocab['keywords'])}, "
            f"marking a significant step in addressing {random.choice(vocab['keywords'])}. "
            f"The {random.choice(vocab['adjectives'])} program aims to "
            f"{random.choice(vocab['verbs'])} key challenges in the coming years."
        )

    @classmethod
    def _generate_paragraphs(
        cls,
        vocab: Dict[str, List[str]],
        fake: Faker,
        num_paragraphs: int,
        noun_density: float
    ) -> str:
        """Generate body paragraphs with appropriate noun density."""
        paragraphs = []

        for _ in range(num_paragraphs):
            # Generate base paragraph
            base_text = fake.paragraph(nb_sentences=random.randint(4, 7))

            # Inject issue-specific vocabulary
            words = base_text.split()
            num_replacements = int(len(words) * noun_density)

            for _ in range(num_replacements):
                if len(words) > 10:
                    idx = random.randint(0, len(words) - 1)
                    words[idx] = random.choice(vocab['keywords'])

            paragraphs.append(' '.join(words))

        return '\n\n'.join(paragraphs)

    @classmethod
    def _generate_quotes(cls, vocab: Dict[str, List[str]], fake: Faker, num_quotes: int) -> str:
        """Generate expert quotes."""
        quotes = []

        for _ in range(num_quotes):
            expert = fake.name()
            quote_templates = [
                f'"{random.choice(vocab["keywords"]).capitalize()} is fundamentally changing how we approach {random.choice(vocab["keywords"])}," says {expert}, expert on {random.choice(vocab["keywords"])}.',
                f'According to {expert}, "The {random.choice(vocab["adjectives"])} nature of {random.choice(vocab["keywords"])} requires immediate action."',
                f'"{random.choice(vocab["entities"])} has demonstrated that {random.choice(vocab["keywords"])} can be both {random.choice(vocab["adjectives"])} and effective," {expert} explains.',
            ]
            quotes.append(random.choice(quote_templates))

        return '\n\n'.join(quotes)

    @classmethod
    def _generate_conclusion(cls, vocab: Dict[str, List[str]], fake: Faker) -> str:
        """Generate conclusion section."""
        return (
            f"In conclusion, {random.choice(vocab['keywords'])} represents both "
            f"challenges and opportunities for {random.choice(vocab['keywords'])}. "
            f"As {random.choice(vocab['entities'])} continues to {random.choice(vocab['verbs'])} "
            f"these {random.choice(vocab['adjectives'])} issues, the path forward requires "
            f"collaborative efforts to {random.choice(vocab['verbs'])} meaningful solutions."
        )

    @classmethod
    def _generate_references(cls, fake: Faker, num_refs: int) -> str:
        """Generate academic references."""
        refs = []
        for i in range(num_refs):
            author = fake.name()
            year = random.randint(2015, 2024)
            title = fake.sentence(nb_words=8).rstrip('.')
            journal = fake.company()
            refs.append(f"{i+1}. {author} ({year}). {title}. {journal}.")

        return '\n'.join(refs)

    @classmethod
    def _generate_recommendations(cls, vocab: Dict[str, List[str]], fake: Faker, num_recs: int) -> str:
        """Generate policy recommendations."""
        recs = []
        for i in range(num_recs):
            rec = (
                f"{i+1}. {random.choice(vocab['verbs']).capitalize()} {random.choice(vocab['keywords'])} "
                f"to ensure {random.choice(vocab['adjectives'])} outcomes."
            )
            recs.append(rec)

        return '\n'.join(recs)

    @classmethod
    def _generate_features(cls, vocab: Dict[str, List[str]], fake: Faker, num_features: int) -> str:
        """Generate feature list for landing page."""
        features = []
        for _ in range(num_features):
            feature = (
                f"✓ {random.choice(vocab['adjectives']).capitalize()} {random.choice(vocab['keywords'])} "
                f"for better {random.choice(vocab['keywords'])}"
            )
            features.append(feature)

        return '\n'.join(features)

    @classmethod
    def _generate_cta(cls, vocab: Dict[str, List[str]], fake: Faker) -> str:
        """Generate call-to-action."""
        templates = [
            f"Start {random.choice(vocab['verbs'])}ing {random.choice(vocab['keywords'])} today!",
            f"Join {random.choice(vocab['entities'])} in {random.choice(vocab['verbs'])}ing {random.choice(vocab['keywords'])}.",
            f"Learn more about our {random.choice(vocab['adjectives'])} {random.choice(vocab['keywords'])} solutions.",
        ]
        return random.choice(templates)

    @classmethod
    def _generate_generic_section(cls, vocab: Dict[str, List[str]], fake: Faker, word_count: int) -> str:
        """Generate generic section content."""
        return fake.text(max_nb_chars=word_count * 6)  # Approximate words to chars

    @classmethod
    def _wrap_in_html(cls, content_data: Dict[str, Any], url: str) -> str:
        """Wrap content in realistic HTML structure."""
        sections_html = ""
        for section_data in content_data['sections']:
            section = section_data['section']
            text = section_data['text']

            if section in ['headline', 'title']:
                sections_html += f"<h1>{text}</h1>\n"
            elif section in ['abstract', 'executive_summary']:
                sections_html += f"<div class='abstract'><p>{text}</p></div>\n"
            else:
                # Split into paragraphs if multiple
                paragraphs = text.split('\n\n')
                sections_html += f"<section class='{section}'>\n"
                for para in paragraphs:
                    sections_html += f"<p>{para}</p>\n"
                sections_html += "</section>\n"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{content_data.get('title', 'Document')}</title>
</head>
<body>
    <article>
        {sections_html}
    </article>
</body>
</html>"""

        return html

    @classmethod
    def _extract_text(cls, content_data: Dict[str, Any]) -> str:
        """Extract plain text from content data."""
        return content_data.get('text', '')

    @classmethod
    def _generate_related_url(cls, base_url: str, index: int) -> str:
        """Generate related URL based on base URL."""
        parsed = urlparse(base_url)
        fake = Faker()

        # Generate related path
        related_paths = [
            f'/related/{fake.slug()}',
            f'/more/{fake.slug()}',
            f'/article/{fake.slug()}',
            f'/page/{index}',
        ]

        new_path = random.choice(related_paths)
        return f"{parsed.scheme}://{parsed.netloc}{new_path}"

    @classmethod
    def _detect_language_from_url(cls, url: str) -> str:
        """Detect language from URL."""
        if any(danish_domain in url for danish_domain in ['.dk', 'denmark', 'danish']):
            return 'da'
        return 'en'
