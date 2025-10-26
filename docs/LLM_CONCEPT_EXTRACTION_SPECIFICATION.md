# LLM-Based Concept Extraction - Technical Specification

## Overview

This specification defines the technical implementation for LLM-based concept extraction from website content. The system distills high-level conceptual themes from the **full textual content** of all pages belonging to a website, creating meaningful abstractions for use in website-concept networks.

**Key Distinction**: This is the "advanced" concept extraction method that considers full context, as opposed to the "simple" noun-based approach. All text content from all scraped pages (level 1, 2, or 3 scraping) under a website domain is aggregated and processed by the LLM to identify high-level concepts.

## 1. LLM Selection

### Primary Model: OpenAI GPT-4o-mini
**Rationale:**
- **Cost-effective**: $0.150 per 1M input tokens, $0.600 per 1M output tokens (95% cheaper than GPT-4)
- **Fast**: ~1-2 second response time for typical requests
- **Capable**: Strong performance on summarization and concept extraction tasks
- **Reliable API**: High availability, rate limits suitable for batch processing
- **Token efficiency**: 128K context window allows processing multiple noun phrases in single request

**Alternative Models (Fallback Order):**
1. **Anthropic Claude 3 Haiku**: Similar pricing, excellent reasoning
2. **Ollama (Local LLM)**: Open-source models (llama3.1, mistral, qwen), no API cost but requires compute
3. **Rule-based Clustering**: Semantic clustering of nouns as fallback
4. **Top Nouns**: Last resort, return most frequent/important nouns as concepts

### Configuration
```python
DEFAULT_MODEL = "gpt-4o-mini"
FALLBACK_MODELS = ["claude-3-haiku-20240307", "ollama:llama3.1", "clustering", "top_nouns"]
MAX_TOKENS = 500  # Concepts are concise
TEMPERATURE = 0.3  # Low temperature for consistent, focused output
MAX_CONTENT_LENGTH = 120000  # ~120K tokens (within GPT-4o-mini 128K context limit)
CHUNK_SIZE = 100000  # For content exceeding max length
```

## 2. Prompt Engineering

### 2.1 Main Extraction Prompt

The prompt uses few-shot learning with clear instructions to ensure consistent output:

```python
CONCEPT_EXTRACTION_PROMPT = """You are an expert research assistant specializing in digital methods and content analysis. Your task is to analyze the full textual content from a website and distill it into 3-7 high-level conceptual themes that represent the core topics and ideas discussed across all pages of the website.

Guidelines:
1. Read and comprehend the entire website content provided
2. Identify overarching themes that capture the main topics and purpose
3. Use clear, academic language suitable for research networks
4. Concepts should be 2-5 words each
5. Focus on substantive topics, not generic web elements (e.g., "Navigation", "Contact")
6. Maintain the semantic essence of the original content
7. Consider the language context (Danish/English/etc.)
8. Look for recurring topics, key arguments, and central themes

Examples:

Input: [Website about climate change with content discussing CO2 emissions, renewable energy sources like wind and solar power, sustainability initiatives, green transitions, fossil fuel reduction, and international climate agreements]
Language: Danish
Output:
- Klimaforandringer og miljø
- Vedvarende energikilder
- Bæredygtig udvikling
- Klimapolitik og aftaler

Input: [Website about artificial intelligence covering machine learning techniques, neural network architectures, deep learning applications, data science methodologies, algorithmic innovation, industrial automation, and robotics development]
Language: English
Output:
- Artificial Intelligence Technologies
- Machine Learning Methods
- Data Science and Analytics
- Automation and Robotics

Now analyze the following website content:

Content: {website_content}
Language: {language}
Output:
"""
```

### 2.2 Refinement Prompt (Optional)

For high-value content or ambiguous results, a second pass refines concepts:

```python
CONCEPT_REFINEMENT_PROMPT = """Review these extracted concepts and ensure they are:
1. Non-overlapping (each represents a distinct theme)
2. At the appropriate abstraction level (not too broad, not too specific)
3. Clearly worded and unambiguous

Original nouns: {noun_phrases}
Initial concepts: {initial_concepts}

Provide refined concepts or confirm the initial ones are optimal.
Refined concepts:
"""
```

### 2.3 Validation Prompt

Used to verify concept quality:

```python
CONCEPT_VALIDATION_PROMPT = """Rate the quality of these extracted concepts on a scale of 1-10:
- Relevance: How well do they capture the source content?
- Distinctness: Are they sufficiently different from each other?
- Clarity: Are they clearly worded and understandable?

Source nouns: {noun_phrases}
Extracted concepts: {concepts}

Provide a single quality score (1-10) and brief reasoning.
Score:
"""
```

## 3. Input Format

### 3.1 Text Aggregation Strategy

The LLM receives the **full textual content** from all pages belonging to a website domain. This requires aggregating text from multiple scraped pages and preparing it for LLM processing.

```python
from typing import List, Dict, Optional, Tuple
import tiktoken

class WebsiteContentAggregator:
    """Aggregate and prepare full website content for LLM processing"""

    def __init__(self, encoding_name: str = "cl100k_base"):
        self.tokenizer = tiktoken.get_encoding(encoding_name)
        self.max_tokens = 120000  # Leave buffer from 128K limit

    async def aggregate_website_content(
        self,
        website_id: int,
        db_session
    ) -> Tuple[str, Dict[str, any]]:
        """
        Aggregate all scraped content for a website.

        Args:
            website_id: ID of the website
            db_session: Database session

        Returns:
            (aggregated_text, metadata)
        """
        from sqlalchemy import select
        from app.models import ScrapedLink, WebsiteContent

        # Get all scraped links for this website
        stmt = select(ScrapedLink).where(
            ScrapedLink.website_id == website_id,
            ScrapedLink.scrape_status == 'completed'
        ).order_by(
            ScrapedLink.depth.asc(),  # Start with level 1
            ScrapedLink.scraped_at.desc()  # Most recent first
        )

        result = await db_session.execute(stmt)
        links = result.scalars().all()

        # Aggregate text from all pages
        page_contents = []
        total_chars = 0

        for link in links:
            if link.content and link.content.text_content:
                # Clean and normalize text
                text = self._clean_text(link.content.text_content)
                if text:
                    page_contents.append({
                        'url': link.url,
                        'depth': link.depth,
                        'text': text,
                        'char_count': len(text)
                    })
                    total_chars += len(text)

        # Combine all page content
        aggregated_text = self._combine_page_contents(page_contents)

        # Calculate token count
        token_count = len(self.tokenizer.encode(aggregated_text))

        metadata = {
            'website_id': website_id,
            'page_count': len(page_contents),
            'total_chars': total_chars,
            'token_count': token_count,
            'exceeds_limit': token_count > self.max_tokens
        }

        return aggregated_text, metadata

    def _clean_text(self, text: str) -> str:
        """Clean and normalize scraped text"""
        import re

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove common boilerplate patterns
        boilerplate_patterns = [
            r'Cookie Policy.*?Accept',
            r'Privacy Policy.*?(?=\n)',
            r'Terms of Service.*?(?=\n)',
            r'Subscribe to newsletter.*?(?=\n)',
            r'Follow us on.*?(?=\n)',
        ]

        for pattern in boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        return text.strip()

    def _combine_page_contents(self, page_contents: List[Dict]) -> str:
        """Combine content from multiple pages with structure"""
        if not page_contents:
            return ""

        # Prioritize by depth (level 1 pages first)
        page_contents.sort(key=lambda x: (x['depth'], -x['char_count']))

        combined_parts = []

        for i, page in enumerate(page_contents):
            # Add subtle separator between pages
            if i > 0:
                combined_parts.append("\n---\n")

            # Add page text
            combined_parts.append(page['text'])

        return "".join(combined_parts)
```

### 3.2 Chunking and Summarization Strategy

When website content exceeds token limits, we need strategies to handle large volumes:

```python
class ContentChunkingStrategy:
    """Handle websites with content exceeding LLM context limits"""

    def __init__(self, max_tokens: int = 120000):
        self.max_tokens = max_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def process_large_content(
        self,
        content: str,
        website_id: int,
        language: str
    ) -> List[str]:
        """
        Process content that exceeds token limits.

        Strategy:
        1. If content < 120K tokens: Use directly
        2. If content 120K-500K tokens: Summarize first, then extract
        3. If content > 500K tokens: Chunk, summarize each, combine, then extract

        Args:
            content: Full website text
            website_id: Website identifier
            language: Content language

        Returns:
            List of text chunks ready for concept extraction
        """
        token_count = len(self.tokenizer.encode(content))

        if token_count <= self.max_tokens:
            # Content fits in context window
            return [content]

        elif token_count <= 500000:
            # Moderate size: Summarize first
            logger.info(
                f"Website {website_id} has {token_count} tokens, "
                "applying summarization"
            )
            summarized = await self._summarize_content(
                content,
                target_length=self.max_tokens // 2
            )
            return [summarized]

        else:
            # Very large: Chunk → summarize each → combine
            logger.info(
                f"Website {website_id} has {token_count} tokens, "
                "applying chunking and summarization"
            )
            return await self._chunk_and_summarize(content)

    async def _summarize_content(
        self,
        content: str,
        target_length: int
    ) -> str:
        """
        Summarize content to target token length using LLM.

        Args:
            content: Text to summarize
            target_length: Target token count

        Returns:
            Summarized text
        """
        import openai

        summarization_prompt = f"""Summarize the following website content, preserving all main topics, themes, and key information. Focus on substantive content and core messages. Target length: approximately {target_length * 4} words.

Content:
{content}

Summary:"""

        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at content summarization."},
                {"role": "user", "content": summarization_prompt}
            ],
            temperature=0.3,
            max_tokens=target_length
        )

        return response.choices[0].message.content

    async def _chunk_and_summarize(
        self,
        content: str,
        chunk_size: int = 100000
    ) -> List[str]:
        """
        Chunk content, summarize each chunk, then combine.

        Args:
            content: Full content
            chunk_size: Tokens per chunk

        Returns:
            List with single combined summary
        """
        # Split into chunks
        tokens = self.tokenizer.encode(content)
        chunks = []

        for i in range(0, len(tokens), chunk_size):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        logger.info(f"Split content into {len(chunks)} chunks")

        # Summarize each chunk
        summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
            summary = await self._summarize_content(
                chunk,
                target_length=10000  # 10K tokens per chunk summary
            )
            summaries.append(summary)

        # Combine summaries
        combined_summary = "\n\n".join(summaries)

        # If combined summaries still too long, summarize again
        combined_tokens = len(self.tokenizer.encode(combined_summary))
        if combined_tokens > self.max_tokens:
            logger.info("Combined summaries still too long, applying final summarization")
            final_summary = await self._summarize_content(
                combined_summary,
                target_length=self.max_tokens // 2
            )
            return [final_summary]

        return [combined_summary]
```

### 3.3 Data Preparation Pipeline

```python
class ConceptExtractionInput:
    """Structured input for LLM concept extraction"""

    def __init__(
        self,
        website_id: int,
        website_content: str,
        language: str,
        page_count: int = 1,
        token_count: int = 0,
        was_summarized: bool = False
    ):
        self.website_id = website_id
        self.website_content = website_content
        self.language = language
        self.page_count = page_count
        self.token_count = token_count
        self.was_summarized = was_summarized

    def prepare_for_llm(self) -> str:
        """
        Prepare website content for LLM input.

        Returns:
            Formatted content ready for concept extraction prompt
        """
        return self.website_content
```

### 3.4 Ollama Integration

Ollama provides local LLM deployment as a fallback when API-based LLMs fail or for high-volume processing to reduce costs:

```python
import httpx
from typing import Optional

class OllamaClient:
    """Client for Ollama local LLM service"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        timeout: int = 300
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> str:
        """
        Generate text using Ollama API.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text

        Raises:
            OllamaError: If generation fails
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "stream": False
                }
            )
            response.raise_for_status()

            result = response.json()
            return result.get("response", "")

        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            raise OllamaError(f"Ollama generation failed: {e}")

    async def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except:
            return False

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class OllamaError(Exception):
    """Ollama-specific error"""
    pass


class OllamaConceptExtractor:
    """Concept extraction using Ollama local LLM"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1"
    ):
        self.client = OllamaClient(base_url, model)

    async def extract_concepts(
        self,
        website_content: str,
        language: str
    ) -> List[ExtractedConcept]:
        """
        Extract concepts using Ollama.

        Args:
            website_content: Full website text
            language: Content language

        Returns:
            List of extracted concepts
        """
        # Check if Ollama is available
        if not await self.client.is_available():
            raise OllamaError("Ollama service not available")

        # Use same prompt as main extraction
        prompt = CONCEPT_EXTRACTION_PROMPT.format(
            website_content=website_content,
            language=language
        )

        # Generate
        response = await self.client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )

        # Parse response
        parser = ConceptParser()
        concepts = parser.parse_response(response)

        # Lower confidence for Ollama results
        for concept in concepts:
            concept.confidence = min(concept.confidence, 0.7)

        return concepts
```

## 4. Output Format

### 4.1 LLM Response Parsing

```python
from typing import List, Optional
from pydantic import BaseModel, Field, validator

class ExtractedConcept(BaseModel):
    """Single extracted concept"""
    text: str = Field(..., min_length=2, max_length=500)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @validator('text')
    def validate_text(cls, v):
        # Clean and normalize
        v = v.strip()
        # Remove leading dashes or bullets
        v = v.lstrip('-•*').strip()
        # Ensure proper capitalization
        if v and not v[0].isupper():
            v = v.capitalize()
        return v


class ConceptExtractionResult(BaseModel):
    """Complete result from concept extraction"""
    website_id: int
    content_id: int
    concepts: List[ExtractedConcept]
    language: str
    model_used: str
    token_count: int
    processing_time: float
    quality_score: Optional[float] = None
    error: Optional[str] = None

    @validator('concepts')
    def validate_concepts(cls, v):
        if len(v) < 2:
            raise ValueError("Must extract at least 2 concepts")
        if len(v) > 10:
            raise ValueError("Too many concepts, limit to 10")
        return v


class ConceptParser:
    """Parse LLM output into structured concepts"""

    def parse_response(
        self,
        response_text: str,
        fallback_on_error: bool = True
    ) -> List[ExtractedConcept]:
        """
        Parse LLM response into ExtractedConcept objects.

        Handles multiple output formats:
        - Bulleted lists (-, *, •)
        - Numbered lists (1., 2., etc.)
        - Line-separated
        - JSON arrays (if LLM outputs JSON)
        """
        concepts = []

        # Try JSON parsing first
        try:
            import json
            data = json.loads(response_text)
            if isinstance(data, list):
                concepts = [
                    ExtractedConcept(text=item)
                    for item in data
                    if isinstance(item, str)
                ]
                if concepts:
                    return concepts
        except json.JSONDecodeError:
            pass

        # Parse as text
        lines = response_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove common prefixes
            line = self._remove_prefixes(line)

            if len(line) >= 2 and len(line) <= 500:
                concepts.append(ExtractedConcept(text=line))

        if not concepts and fallback_on_error:
            # Last resort: split by commas
            parts = response_text.split(',')
            concepts = [
                ExtractedConcept(text=p.strip())
                for p in parts
                if 2 <= len(p.strip()) <= 500
            ]

        return concepts

    def _remove_prefixes(self, text: str) -> str:
        """Remove common list prefixes"""
        import re
        # Remove bullets, numbers, dashes
        patterns = [
            r'^[-•*]\s*',  # bullets
            r'^\d+\.\s*',  # numbers
            r'^[a-z]\)\s*',  # letters
        ]
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text.strip()
```

### 4.2 Response Validation

```python
class ConceptValidator:
    """Validate extracted concepts for quality"""

    def __init__(self):
        self.min_concepts = 2
        self.max_concepts = 10
        self.min_length = 2
        self.max_length = 500

    def validate(
        self,
        concepts: List[ExtractedConcept],
        source_nouns: List[str]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate concept extraction results.

        Returns:
            (is_valid, error_message)
        """
        # Check count
        if len(concepts) < self.min_concepts:
            return False, f"Too few concepts: {len(concepts)}"

        if len(concepts) > self.max_concepts:
            return False, f"Too many concepts: {len(concepts)}"

        # Check for duplicates
        concept_texts = [c.text.lower() for c in concepts]
        if len(concept_texts) != len(set(concept_texts)):
            return False, "Duplicate concepts found"

        # Check individual concepts
        for concept in concepts:
            if len(concept.text) < self.min_length:
                return False, f"Concept too short: '{concept.text}'"

            if len(concept.text) > self.max_length:
                return False, f"Concept too long: '{concept.text}'"

        # Check semantic relevance (basic)
        if source_nouns:
            relevance_score = self._calculate_relevance(
                concepts, source_nouns
            )
            if relevance_score < 0.2:
                return False, f"Concepts not relevant to source (score: {relevance_score})"

        return True, None

    def _calculate_relevance(
        self,
        concepts: List[ExtractedConcept],
        source_nouns: List[str]
    ) -> float:
        """
        Calculate semantic relevance between concepts and source nouns.
        Simple word overlap heuristic.
        """
        concept_words = set()
        for concept in concepts:
            words = concept.text.lower().split()
            concept_words.update(words)

        source_words = set(noun.lower() for noun in source_nouns)

        if not concept_words or not source_words:
            return 0.0

        overlap = len(concept_words & source_words)
        return overlap / min(len(concept_words), len(source_words))
```

## 5. Caching Strategy

### 5.1 Multi-Level Caching

```python
from typing import Optional
import hashlib
import json
from datetime import datetime, timedelta

class ConceptCache:
    """Multi-level caching for concept extraction results"""

    def __init__(
        self,
        redis_client,
        db_session,
        ttl_hours: int = 168  # 1 week default
    ):
        self.redis = redis_client
        self.db = db_session
        self.ttl_seconds = ttl_hours * 3600

    def get_cache_key(
        self,
        website_id: int,
        content_hash: str,
        model: str,
        temperature: float
    ) -> str:
        """
        Generate deterministic cache key.

        Key factors:
        - Website ID (identifies the website)
        - Content hash (aggregated text content hash - input changes = cache miss)
        - Model and temperature (config changes = cache miss)
        """
        key = f"concept:v2:website:{website_id}:{content_hash}:{model}:{temperature}"
        return key

    def hash_content(self, content: str) -> str:
        """
        Generate content hash for caching.

        Args:
            content: Full website text content

        Returns:
            MD5 hash of content
        """
        return hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()

    async def get(
        self,
        website_id: int,
        content: str,
        model: str,
        temperature: float
    ) -> Optional[ConceptExtractionResult]:
        """
        Retrieve cached result.

        Checks Redis first (fast), then database (persistent).
        """
        content_hash = self.hash_content(content)
        cache_key = self.get_cache_key(
            website_id, content_hash, model, temperature
        )

        # Try Redis (L1 cache)
        redis_data = await self.redis.get(cache_key)
        if redis_data:
            return ConceptExtractionResult.parse_raw(redis_data)

        # Try database (L2 cache)
        db_result = await self._get_from_db(content_id, cache_key)
        if db_result:
            # Populate Redis for next time
            await self.redis.setex(
                cache_key,
                self.ttl_seconds,
                db_result.json()
            )
            return db_result

        return None

    async def set(
        self,
        content_id: int,
        noun_phrases: List[str],
        model: str,
        temperature: float,
        result: ConceptExtractionResult
    ) -> None:
        """
        Store result in both cache layers.
        """
        cache_key = self.get_cache_key(
            content_id, noun_phrases, model, temperature
        )

        # Store in Redis (fast access)
        await self.redis.setex(
            cache_key,
            self.ttl_seconds,
            result.json()
        )

        # Store in database (persistent)
        await self._save_to_db(content_id, cache_key, result)

    async def _get_from_db(
        self,
        content_id: int,
        cache_key: str
    ) -> Optional[ConceptExtractionResult]:
        """Retrieve from database"""
        # Query extracted_concepts table
        from sqlalchemy import select
        from app.models import ExtractedConcept as DBConcept

        stmt = select(DBConcept).where(
            DBConcept.content_id == content_id
        ).order_by(DBConcept.created_at.desc())

        result = await self.db.execute(stmt)
        concepts = result.scalars().all()

        if concepts:
            # Reconstruct result object
            return ConceptExtractionResult(
                website_id=concepts[0].website_id,
                content_id=content_id,
                concepts=[
                    ExtractedConcept(
                        text=c.concept,
                        confidence=c.relevance_score
                    )
                    for c in concepts
                ],
                language=concepts[0].language or "unknown",
                model_used="cached",
                token_count=0,
                processing_time=0.0
            )

        return None

    async def _save_to_db(
        self,
        content_id: int,
        cache_key: str,
        result: ConceptExtractionResult
    ) -> None:
        """Save to database for persistent cache"""
        # Concepts are saved to extracted_concepts table
        # in the main extraction workflow
        pass

    async def invalidate(self, content_id: int) -> None:
        """
        Invalidate all cached results for a content ID.

        Use when content is re-scraped or re-processed.
        """
        # Pattern match in Redis
        pattern = f"concept:v1:{content_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

### 5.2 Cache Warming Strategy

```python
class CacheWarmer:
    """Pre-populate cache for frequently accessed content"""

    async def warm_popular_content(
        self,
        db_session,
        concept_extractor,
        limit: int = 100
    ) -> None:
        """
        Pre-extract concepts for most viewed/accessed content.

        Run as periodic background task (e.g., nightly).
        """
        from sqlalchemy import select, func
        from app.models import WebsiteContent

        # Find most accessed content without concepts
        stmt = select(WebsiteContent).where(
            ~WebsiteContent.extracted_concepts.any()
        ).order_by(
            WebsiteContent.access_count.desc()  # Assuming you track this
        ).limit(limit)

        result = await db_session.execute(stmt)
        content_items = result.scalars().all()

        for content in content_items:
            try:
                await concept_extractor.extract_concepts(
                    content_id=content.id,
                    force_refresh=False
                )
            except Exception as e:
                logger.error(
                    f"Cache warming failed for content {content.id}: {e}"
                )
```

## 6. Error Handling

### 6.1 Retry Strategy

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import openai

class ConceptExtractor:
    """Main concept extraction service with robust error handling"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            openai.error.RateLimitError,
            openai.error.APIError,
            openai.error.Timeout,
            openai.error.ServiceUnavailableError
        ))
    )
    async def _call_llm_api(
        self,
        prompt: str,
        model: str,
        temperature: float
    ) -> str:
        """
        Call LLM API with automatic retry.

        Retries on transient errors:
        - Rate limits (waits exponentially)
        - Timeouts
        - Service unavailable

        Does NOT retry on:
        - Invalid API key
        - Invalid request format
        - Content policy violations
        """
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert research assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature,
            max_tokens=500,
            timeout=30  # 30 second timeout
        )

        return response.choices[0].message.content
```

### 6.2 Fallback Mechanisms

```python
class FallbackConceptExtractor:
    """Fallback extraction methods when LLM fails"""

    def __init__(self):
        self.nlp = None  # spaCy model

    async def extract_with_fallback(
        self,
        website_content: str,
        language: str,
        website_id: int
    ) -> List[ExtractedConcept]:
        """
        Multi-stage fallback strategy:

        1. Try primary LLM (GPT-4o-mini)
        2. Try fallback LLM (Claude Haiku)
        3. Try Ollama (local LLM)
        4. Try rule-based clustering on extracted nouns
        5. Return top TF-IDF nouns as fallback
        """
        # Stage 1: Primary LLM
        try:
            result = await self._extract_with_llm(
                website_content,
                language,
                model="gpt-4o-mini"
            )
            if result:
                for concept in result:
                    concept.confidence = 1.0
                return result
        except Exception as e:
            logger.warning(f"Primary LLM failed for website {website_id}: {e}")

        # Stage 2: Fallback LLM (Claude)
        try:
            result = await self._extract_with_llm(
                website_content,
                language,
                model="claude-3-haiku-20240307"
            )
            if result:
                for concept in result:
                    concept.confidence = 0.9
                return result
        except Exception as e:
            logger.warning(f"Claude fallback failed for website {website_id}: {e}")

        # Stage 3: Ollama (Local LLM)
        try:
            ollama_extractor = OllamaConceptExtractor()
            result = await ollama_extractor.extract_concepts(
                website_content,
                language
            )
            if result:
                for concept in result:
                    concept.confidence = 0.7
                return result
        except Exception as e:
            logger.warning(f"Ollama fallback failed for website {website_id}: {e}")

        # Stage 4: Rule-based clustering (extract nouns first)
        try:
            # Extract nouns from content using spaCy
            nouns = await self._extract_nouns_from_content(website_content, language)
            result = await self._extract_with_clustering(
                nouns,
                language
            )
            if result:
                for concept in result:
                    concept.confidence = 0.5
                return result
        except Exception as e:
            logger.warning(f"Clustering fallback failed for website {website_id}: {e}")

        # Stage 5: Last resort - return top nouns
        try:
            nouns = await self._extract_nouns_from_content(website_content, language)
            result = self._extract_top_nouns_as_concepts(nouns)
            for concept in result:
                concept.confidence = 0.3
            return result
        except Exception as e:
            logger.error(f"All fallbacks failed for website {website_id}: {e}")
            return []

    async def _extract_nouns_from_content(
        self,
        content: str,
        language: str
    ) -> List[str]:
        """
        Extract noun phrases from content using spaCy.

        Args:
            content: Full website text
            language: Content language

        Returns:
            List of noun phrases
        """
        import spacy
        from collections import Counter

        # Load appropriate spaCy model
        if language == "da":
            nlp = spacy.load("da_core_news_sm")
        elif language == "en":
            nlp = spacy.load("en_core_web_sm")
        else:
            nlp = spacy.load("xx_ent_wiki_sm")  # Multilingual

        # Process text (limit to first 1M chars for performance)
        doc = nlp(content[:1000000])

        # Extract nouns and noun phrases
        nouns = []
        for chunk in doc.noun_chunks:
            nouns.append(chunk.text.lower())

        # Get most common nouns
        noun_counts = Counter(nouns)
        top_nouns = [noun for noun, count in noun_counts.most_common(100)]

        return top_nouns

    async def _extract_with_clustering(
        self,
        noun_phrases: List[str],
        language: str
    ) -> List[ExtractedConcept]:
        """
        Rule-based concept extraction using clustering.

        Uses semantic similarity to group related nouns,
        then selects representative terms as concepts.
        """
        from sklearn.cluster import KMeans
        from sentence_transformers import SentenceTransformer

        # Encode nouns
        model = SentenceTransformer(
            'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
        )
        embeddings = model.encode(noun_phrases)

        # Cluster into 3-7 groups
        n_clusters = min(max(3, len(noun_phrases) // 10), 7)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # Extract representative nouns from each cluster
        concepts = []
        for cluster_id in range(n_clusters):
            cluster_nouns = [
                noun for noun, label in zip(noun_phrases, labels)
                if label == cluster_id
            ]

            if cluster_nouns:
                # Use most central noun as concept
                representative = cluster_nouns[0]  # Simplified
                concepts.append(
                    ExtractedConcept(
                        text=representative.capitalize(),
                        confidence=0.5  # Lower confidence for fallback
                    )
                )

        return concepts

    def _extract_top_nouns_as_concepts(
        self,
        noun_phrases: List[str]
    ) -> List[ExtractedConcept]:
        """
        Last resort: return top nouns directly as concepts.
        """
        top_nouns = noun_phrases[:7]  # Take top 7
        return [
            ExtractedConcept(
                text=noun.capitalize(),
                confidence=0.3  # Low confidence
            )
            for noun in top_nouns
        ]
```

### 6.3 Error Logging and Monitoring

```python
import structlog

logger = structlog.get_logger(__name__)

class ConceptExtractionMonitor:
    """Monitor concept extraction performance and errors"""

    async def log_extraction_attempt(
        self,
        content_id: int,
        noun_count: int,
        success: bool,
        model: str,
        duration: float,
        error: Optional[str] = None
    ) -> None:
        """
        Log extraction attempt with structured logging.

        Enables monitoring of:
        - Success rates per model
        - Performance metrics
        - Common error patterns
        - Cost tracking
        """
        logger.info(
            "concept_extraction_attempt",
            content_id=content_id,
            noun_count=noun_count,
            success=success,
            model=model,
            duration_seconds=duration,
            error=error
        )

        # Track metrics for alerting
        if not success:
            await self._increment_error_counter(model, error)

    async def _increment_error_counter(
        self,
        model: str,
        error: str
    ) -> None:
        """Increment error counter in Redis for monitoring"""
        # Implementation depends on monitoring setup
        pass
```

## 7. Rate Limiting

### 7.1 API Rate Limiter

```python
from asyncio import Semaphore, sleep
from datetime import datetime, timedelta
from collections import deque

class APIRateLimiter:
    """
    Rate limiter for LLM API calls.

    Enforces both:
    - Requests per minute (RPM)
    - Tokens per minute (TPM)
    """

    def __init__(
        self,
        rpm_limit: int = 10000,  # OpenAI tier-based
        tpm_limit: int = 2000000,  # OpenAI tier-based
        burst_size: int = 50  # Allow bursts
    ):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.burst_semaphore = Semaphore(burst_size)

        # Sliding window counters
        self.request_times: deque = deque()
        self.token_times: deque = deque()
        self.lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000) -> None:
        """
        Acquire permission to make API call.

        Blocks if rate limits would be exceeded.
        """
        async with self.burst_semaphore:
            async with self.lock:
                now = datetime.now()

                # Clean old entries (older than 1 minute)
                cutoff = now - timedelta(minutes=1)
                self._clean_old_entries(cutoff)

                # Check if we need to wait
                while self._would_exceed_limits(estimated_tokens):
                    await sleep(0.1)
                    now = datetime.now()
                    cutoff = now - timedelta(minutes=1)
                    self._clean_old_entries(cutoff)

                # Record this request
                self.request_times.append(now)
                for _ in range(estimated_tokens):
                    self.token_times.append(now)

    def _clean_old_entries(self, cutoff: datetime) -> None:
        """Remove entries older than cutoff"""
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()

        while self.token_times and self.token_times[0] < cutoff:
            self.token_times.popleft()

    def _would_exceed_limits(self, estimated_tokens: int) -> bool:
        """Check if adding this request would exceed limits"""
        if len(self.request_times) >= self.rpm_limit:
            return True

        if len(self.token_times) + estimated_tokens > self.tpm_limit:
            return True

        return False

    async def release(self, actual_tokens: int, estimated_tokens: int) -> None:
        """
        Adjust token count after actual usage is known.

        If we overestimated, credits more capacity.
        """
        async with self.lock:
            token_diff = actual_tokens - estimated_tokens
            if token_diff < 0:
                # Remove excess token entries
                for _ in range(abs(token_diff)):
                    if self.token_times:
                        self.token_times.pop()
            elif token_diff > 0:
                # Add missing token entries
                now = datetime.now()
                for _ in range(token_diff):
                    self.token_times.append(now)
```

### 7.2 Per-User Rate Limiting

```python
class UserRateLimiter:
    """
    Per-user rate limiting for concept extraction.

    Prevents individual users from consuming excessive API quota.
    """

    def __init__(
        self,
        redis_client,
        extractions_per_hour: int = 100,
        extractions_per_day: int = 1000
    ):
        self.redis = redis_client
        self.extractions_per_hour = extractions_per_hour
        self.extractions_per_day = extractions_per_day

    async def check_and_increment(self, user_id: int) -> tuple[bool, str]:
        """
        Check if user can make extraction request.

        Returns:
            (allowed, message)
        """
        # Check hourly limit
        hour_key = f"rate:concept:user:{user_id}:hour"
        hour_count = await self.redis.incr(hour_key)

        if hour_count == 1:
            # First request this hour, set expiry
            await self.redis.expire(hour_key, 3600)

        if hour_count > self.extractions_per_hour:
            return False, "Hourly rate limit exceeded"

        # Check daily limit
        day_key = f"rate:concept:user:{user_id}:day"
        day_count = await self.redis.incr(day_key)

        if day_count == 1:
            # First request today, set expiry
            await self.redis.expire(day_key, 86400)

        if day_count > self.extractions_per_day:
            return False, "Daily rate limit exceeded"

        return True, "OK"
```

## 8. Database Schema Additions

### 8.1 Concept Metadata Table

```sql
-- Add columns to extracted_concepts table for LLM metadata
ALTER TABLE extracted_concepts
ADD COLUMN model_used VARCHAR(50) NULL,
ADD COLUMN temperature FLOAT NULL,
ADD COLUMN token_count INTEGER NULL,
ADD COLUMN processing_time FLOAT NULL,
ADD COLUMN cache_hit BOOLEAN DEFAULT FALSE,
ADD COLUMN quality_score FLOAT NULL,
ADD COLUMN extraction_method VARCHAR(20) DEFAULT 'llm',  -- 'llm', 'ollama', 'clustering', 'fallback'
ADD COLUMN raw_llm_response TEXT NULL,  -- For debugging/reprocessing
ADD COLUMN page_count INTEGER DEFAULT 1,  -- Number of pages processed
ADD COLUMN was_summarized BOOLEAN DEFAULT FALSE;  -- Whether content was summarized before extraction

-- Index for monitoring and analytics
CREATE INDEX idx_extracted_concepts_model ON extracted_concepts(model_used);
CREATE INDEX idx_extracted_concepts_method ON extracted_concepts(extraction_method);
CREATE INDEX idx_extracted_concepts_quality ON extracted_concepts(quality_score);
```

### 8.2 Concept Cache Table

```sql
-- Optional: dedicated cache table for faster lookups
CREATE TABLE concept_extraction_cache (
    id SERIAL PRIMARY KEY,
    website_id INTEGER NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    content_hash VARCHAR(32) NOT NULL,  -- Hash of aggregated website content
    model VARCHAR(50) NOT NULL,
    temperature FLOAT NOT NULL,
    concepts JSONB NOT NULL,  -- Array of concept objects
    token_count INTEGER NOT NULL,
    page_count INTEGER DEFAULT 1,  -- Number of pages aggregated
    was_summarized BOOLEAN DEFAULT FALSE,  -- Whether content was summarized
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_concept_cache_website ON concept_extraction_cache(website_id);
CREATE INDEX idx_concept_cache_key ON concept_extraction_cache(cache_key);
CREATE INDEX idx_concept_cache_content_hash ON concept_extraction_cache(content_hash);
CREATE INDEX idx_concept_cache_expires ON concept_extraction_cache(expires_at);

-- Cleanup expired cache entries (run periodically)
DELETE FROM concept_extraction_cache WHERE expires_at < NOW();
```

### 8.3 Cost Tracking Table

```sql
-- Track API costs for budgeting and analysis
CREATE TABLE llm_api_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    website_id INTEGER REFERENCES websites(id) ON DELETE SET NULL,
    model VARCHAR(50) NOT NULL,
    operation VARCHAR(50) NOT NULL,  -- 'concept_extraction', 'summarization', 'refinement'
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    success BOOLEAN NOT NULL,
    error_type VARCHAR(50) NULL,
    was_summarized BOOLEAN DEFAULT FALSE,  -- Whether this was a summarization call
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_usage_user ON llm_api_usage(user_id);
CREATE INDEX idx_llm_usage_model ON llm_api_usage(model);
CREATE INDEX idx_llm_usage_date ON llm_api_usage(created_at);

-- View for cost analytics
CREATE VIEW v_llm_cost_summary AS
SELECT
    user_id,
    model,
    DATE(created_at) as date,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_requests,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed_requests
FROM llm_api_usage
GROUP BY user_id, model, DATE(created_at);
```

## 9. API Integration

### 9.1 New Endpoint: Extract Concepts

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class ConceptExtractionRequest(BaseModel):
    """Request to extract concepts from content"""
    content_ids: List[int] = Field(..., min_items=1, max_items=100)
    force_refresh: bool = Field(default=False, description="Bypass cache")
    model: Optional[str] = Field(default=None, description="Override default model")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    async_processing: bool = Field(default=False, description="Process in background")


class ConceptExtractionResponse(BaseModel):
    """Response from concept extraction"""
    task_id: Optional[str] = None
    results: Optional[List[ConceptExtractionResult]] = None
    status: str
    message: str


@router.post("/extract-concepts", response_model=ConceptExtractionResponse)
async def extract_concepts(
    request: ConceptExtractionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    concept_extractor: ConceptExtractor = Depends(get_concept_extractor)
):
    """
    Extract high-level concepts from website content using LLM.

    This endpoint:
    1. Retrieves noun phrases from specified content
    2. Calls LLM API to distill concepts
    3. Stores results in database
    4. Returns concepts or task ID for async processing

    Rate limits:
    - 100 extractions per hour per user
    - 1000 extractions per day per user
    """
    # Check rate limits
    rate_limiter = UserRateLimiter(redis_client)
    allowed, message = await rate_limiter.check_and_increment(current_user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=message)

    # Verify content ownership
    from app.repositories import ContentRepository
    content_repo = ContentRepository(db)

    content_items = await content_repo.get_by_ids(
        request.content_ids,
        user_id=current_user.id
    )

    if len(content_items) != len(request.content_ids):
        raise HTTPException(
            status_code=404,
            detail="Some content items not found or unauthorized"
        )

    # Async processing for large batches
    if request.async_processing or len(request.content_ids) > 10:
        from app.tasks import extract_concepts_task

        task = extract_concepts_task.delay(
            content_ids=request.content_ids,
            user_id=current_user.id,
            force_refresh=request.force_refresh,
            model=request.model,
            temperature=request.temperature
        )

        return ConceptExtractionResponse(
            task_id=task.id,
            status="processing",
            message=f"Concept extraction queued for {len(request.content_ids)} items"
        )

    # Synchronous processing for small batches
    results = []
    for content_id in request.content_ids:
        try:
            result = await concept_extractor.extract_concepts(
                content_id=content_id,
                user_id=current_user.id,
                force_refresh=request.force_refresh,
                model=request.model,
                temperature=request.temperature
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Concept extraction failed for {content_id}: {e}")
            results.append(
                ConceptExtractionResult(
                    website_id=0,
                    content_id=content_id,
                    concepts=[],
                    language="unknown",
                    model_used="error",
                    token_count=0,
                    processing_time=0.0,
                    error=str(e)
                )
            )

    return ConceptExtractionResponse(
        results=results,
        status="completed",
        message=f"Extracted concepts from {len(results)} items"
    )


@router.get("/concepts/{content_id}", response_model=ConceptExtractionResult)
async def get_concepts(
    content_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve previously extracted concepts for content.

    Returns cached results if available, otherwise triggers extraction.
    """
    from app.repositories import ConceptRepository

    repo = ConceptRepository(db)
    concepts = await repo.get_by_content_id(
        content_id,
        user_id=current_user.id
    )

    if not concepts:
        raise HTTPException(
            status_code=404,
            detail="Concepts not found. Call /extract-concepts first."
        )

    return ConceptExtractionResult(
        website_id=concepts[0].website_id,
        content_id=content_id,
        concepts=[
            ExtractedConcept(
                text=c.concept,
                confidence=c.relevance_score
            )
            for c in concepts
        ],
        language=concepts[0].language or "unknown",
        model_used=concepts[0].model_used or "unknown",
        token_count=concepts[0].token_count or 0,
        processing_time=0.0
    )
```

### 9.2 Integration with Network Generation

```python
# In /api/network/generate endpoint

@router.post("/generate", response_model=NetworkGenerationResponse)
async def generate_network(
    request: NetworkGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate network graph from scraped data.

    For 'website_concept' type, automatically triggers concept extraction
    if not already performed.
    """
    if request.type == "website_concept":
        # Ensure concepts are extracted before building network
        from app.services import ConceptExtractionService

        concept_service = ConceptExtractionService(db)

        # Get all content IDs for the sessions
        content_ids = await concept_service.get_content_ids_for_sessions(
            request.session_ids,
            user_id=current_user.id
        )

        # Extract concepts (uses cache if available)
        extraction_summary = await concept_service.ensure_concepts_extracted(
            content_ids=content_ids,
            user_id=current_user.id,
            model=request.config.get("llm_model"),
            temperature=request.config.get("llm_temperature")
        )

        logger.info(
            f"Concept extraction: {extraction_summary['cached']} cached, "
            f"{extraction_summary['new']} new, "
            f"{extraction_summary['failed']} failed"
        )

    # Continue with network generation...
    # (existing logic)
```

## 10. Configuration

### 10.1 Environment Variables

```bash
# .env file additions

# LLM Configuration
CONCEPT_EXTRACTION_ENABLED=true
DEFAULT_LLM_MODEL=gpt-4o-mini
FALLBACK_LLM_MODEL=claude-3-haiku-20240307
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=500
MAX_CONTENT_LENGTH=120000  # Token limit for full text

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Ollama Configuration (Local LLM)
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1  # Options: llama3.1, mistral, qwen, etc.
OLLAMA_TIMEOUT=300  # Seconds

# Rate Limiting
LLM_RPM_LIMIT=10000
LLM_TPM_LIMIT=2000000
LLM_BURST_SIZE=50

# User Rate Limits
USER_EXTRACTIONS_PER_HOUR=100
USER_EXTRACTIONS_PER_DAY=1000

# Caching
CONCEPT_CACHE_TTL_HOURS=168  # 1 week
CONCEPT_CACHE_ENABLED=true

# Quality Thresholds
MIN_CONCEPTS=2
MAX_CONCEPTS=10
MIN_CONCEPT_RELEVANCE=0.2

# Content Processing
ENABLE_SUMMARIZATION=true  # For large websites
SUMMARIZATION_THRESHOLD_TOKENS=120000
CHUNK_SIZE_TOKENS=100000

# Cost Tracking
TRACK_LLM_COSTS=true
COST_ALERT_THRESHOLD_USD=100.0  # Daily alert threshold

# Fallback Behavior
ENABLE_OLLAMA_FALLBACK=true
ENABLE_CLUSTERING_FALLBACK=true
ENABLE_NOUN_FALLBACK=true
```

### 10.2 Config Class

```python
from pydantic import BaseSettings, Field
from typing import Optional

class ConceptExtractionConfig(BaseSettings):
    """Configuration for LLM concept extraction"""

    # Core settings
    enabled: bool = Field(default=True, env="CONCEPT_EXTRACTION_ENABLED")
    default_model: str = Field(default="gpt-4o-mini", env="DEFAULT_LLM_MODEL")
    fallback_model: str = Field(
        default="claude-3-haiku-20240307",
        env="FALLBACK_LLM_MODEL"
    )
    temperature: float = Field(default=0.3, env="LLM_TEMPERATURE")
    max_tokens: int = Field(default=500, env="LLM_MAX_TOKENS")
    max_content_length: int = Field(default=120000, env="MAX_CONTENT_LENGTH")

    # API keys
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")

    # Ollama configuration
    ollama_enabled: bool = Field(default=True, env="OLLAMA_ENABLED")
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1", env="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=300, env="OLLAMA_TIMEOUT")

    # Rate limiting
    rpm_limit: int = Field(default=10000, env="LLM_RPM_LIMIT")
    tpm_limit: int = Field(default=2000000, env="LLM_TPM_LIMIT")
    burst_size: int = Field(default=50, env="LLM_BURST_SIZE")

    # User limits
    user_extractions_per_hour: int = Field(
        default=100,
        env="USER_EXTRACTIONS_PER_HOUR"
    )
    user_extractions_per_day: int = Field(
        default=1000,
        env="USER_EXTRACTIONS_PER_DAY"
    )

    # Caching
    cache_ttl_hours: int = Field(default=168, env="CONCEPT_CACHE_TTL_HOURS")
    cache_enabled: bool = Field(default=True, env="CONCEPT_CACHE_ENABLED")

    # Quality
    min_concepts: int = Field(default=2, env="MIN_CONCEPTS")
    max_concepts: int = Field(default=10, env="MAX_CONCEPTS")
    min_relevance: float = Field(default=0.2, env="MIN_CONCEPT_RELEVANCE")

    # Batching
    batch_size: int = Field(default=5, env="CONCEPT_BATCH_SIZE")
    max_nouns_per_batch: int = Field(
        default=200,
        env="CONCEPT_MAX_NOUNS_PER_BATCH"
    )

    # Cost tracking
    track_costs: bool = Field(default=True, env="TRACK_LLM_COSTS")
    cost_alert_threshold: float = Field(
        default=100.0,
        env="COST_ALERT_THRESHOLD_USD"
    )

    # Content processing
    enable_summarization: bool = Field(default=True, env="ENABLE_SUMMARIZATION")
    summarization_threshold: int = Field(default=120000, env="SUMMARIZATION_THRESHOLD_TOKENS")
    chunk_size: int = Field(default=100000, env="CHUNK_SIZE_TOKENS")

    # Fallbacks
    enable_ollama_fallback: bool = Field(
        default=True,
        env="ENABLE_OLLAMA_FALLBACK"
    )
    enable_clustering_fallback: bool = Field(
        default=True,
        env="ENABLE_CLUSTERING_FALLBACK"
    )
    enable_noun_fallback: bool = Field(
        default=True,
        env="ENABLE_NOUN_FALLBACK"
    )

    class Config:
        env_file = ".env"

    def validate_api_keys(self) -> None:
        """Ensure at least one API key is configured"""
        if not self.openai_api_key and not self.anthropic_api_key:
            raise ValueError(
                "At least one LLM API key must be configured "
                "(OPENAI_API_KEY or ANTHROPIC_API_KEY)"
            )

    def get_pricing(self, model: str) -> tuple[float, float]:
        """
        Get pricing for model.

        Returns:
            (input_price_per_1m_tokens, output_price_per_1m_tokens)
        """
        pricing = {
            "gpt-4o-mini": (0.150, 0.600),
            "gpt-3.5-turbo": (0.500, 1.500),
            "claude-3-haiku-20240307": (0.250, 1.250),
            "gpt-4": (30.0, 60.0),  # Expensive!
        }
        return pricing.get(model, (1.0, 2.0))  # Default conservative estimate
```

## Summary

This specification provides a complete, production-ready implementation plan for LLM-based concept extraction using full website content:

1. **Context-aware**: Processes full textual content from all pages of a website
2. **Cost-conscious**: Uses GPT-4o-mini ($0.15 per 1M input tokens) with intelligent chunking
3. **Reliable**: Multi-level fallbacks including Ollama local LLM
4. **Fast**: Caching reduces 90%+ of API calls for unchanged content
5. **Scalable**: Handles large websites through summarization strategies
6. **Quality-assured**: Full context enables better concept extraction than noun-based approach
7. **Research-ready**: Reproducibility through content hashing and versioning

**Estimated Costs (Full Text Processing):**

Assumptions:
- Average website: 5 scraped pages
- Average content per website: ~15,000 tokens (after cleaning)
- Some large websites: 100K+ tokens (requiring summarization)
- Output: ~100 tokens per extraction

Cost per website (typical):
- Input: 15,000 tokens × $0.15/1M = $0.00225
- Output: 100 tokens × $0.60/1M = $0.00006
- **Per website: ~$0.0023** (2.3 cents per 10 websites)

Cost per website (large, with summarization):
- First pass summarization: 100,000 tokens × $0.15/1M = $0.015
- Concept extraction: 50,000 tokens × $0.15/1M = $0.0075
- **Per large website: ~$0.023** (2.3 cents per website)

Scale with 90% cache hit rate:
- **1,000 websites: ~$23 first run, $2.30 subsequent runs**
- **10,000 websites: ~$230 first run, $23 subsequent runs**

**Cost Comparison:**
- Old approach (nouns only): $0.00014 per website
- New approach (full text): $0.0023 per website (16x more expensive)
- **Trade-off**: Significantly better concept quality from full context

**Performance Targets:**
- Cache hit: <50ms per extraction
- Cache miss (typical site): 2-5 seconds per extraction
- Cache miss (large site with summarization): 10-30 seconds per extraction
- Batch processing: 50-100 websites per hour (with rate limiting)
- Quality: >90% semantic relevance (better than noun-based approach)

**Key Differences from Noun-Based Approach:**
- **Input**: Full website text vs. top 50 nouns
- **Context**: Complete understanding vs. keyword-based
- **Quality**: Higher conceptual accuracy
- **Cost**: ~16x higher per website
- **Speed**: Slower due to larger input (but still acceptable for batch processing)
- **Fallback**: Includes Ollama (local LLM) as zero-cost option

**When to Use Which Approach:**
- **Full Text (This Spec)**: Research applications requiring high-quality concepts, websites with rich content
- **Noun-Based (Simple)**: Quick analysis, cost-sensitive applications, websites with limited content
