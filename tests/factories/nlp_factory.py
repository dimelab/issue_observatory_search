"""
NLPDataFactory - Generate realistic synthetic NLP extraction results.

This factory generates NLP analysis results that mimic real extraction:
- Noun extraction with Zipf's law frequency distribution
- TF-IDF scores following power law
- Named Entity Recognition (PERSON, ORG, LOC, DATE)
- Support for Danish and English vocabularies
- Confidence scores and lemmatization
- Realistic entity co-occurrence patterns
"""
from typing import Dict, List, Optional, Any
import random
import numpy as np
from faker import Faker

from .base import (
    set_seed,
    get_issue_vocabulary,
    generate_zipf_distribution,
    generate_realistic_tfidf_scores,
    generate_zipf_frequencies
)


class NLPDataFactory:
    """Generate synthetic NLP extraction results."""

    # Base vocabulary pools
    DANISH_NOUNS = [
        'energi', 'vindmølle', 'klima', 'bæredygtighed', 'forskning',
        'teknologi', 'miljø', 'udvikling', 'samfund', 'økonomi',
        'politik', 'virksomhed', 'projekt', 'system', 'løsning',
        'marked', 'investering', 'innovation', 'strategi', 'ressource',
        'område', 'effekt', 'produktion', 'kapacitet', 'infrastruktur',
        'regering', 'organisation', 'institut', 'universitet', 'centrum'
    ]

    ENGLISH_NOUNS = [
        'energy', 'climate', 'technology', 'research', 'policy',
        'sustainability', 'innovation', 'development', 'system', 'analysis',
        'impact', 'change', 'solution', 'challenge', 'opportunity',
        'market', 'investment', 'growth', 'strategy', 'resource',
        'government', 'organization', 'sector', 'industry', 'framework',
        'approach', 'method', 'data', 'evidence', 'assessment'
    ]

    # Named entity pools
    ENTITIES = {
        'PERSON': [
            'Anders Fogh Rasmussen', 'Greta Thunberg', 'Bill Gates', 'Elon Musk',
            'Angela Merkel', 'Joe Biden', 'Xi Jinping', 'Emmanuel Macron',
            'Ursula von der Leyen', 'António Guterres', 'Sundar Pichai',
            'Satya Nadella', 'Tim Cook', 'Mark Zuckerberg', 'Jeff Bezos',
            'Lars Løkke Rasmussen', 'Mette Frederiksen', 'Margrethe Vestager'
        ],
        'ORG': [
            'European Union', 'Vestas', 'Ørsted', 'Google', 'Microsoft',
            'United Nations', 'WHO', 'IPCC', 'European Commission',
            'World Bank', 'IMF', 'Greenpeace', 'WWF', 'NASA',
            'MIT', 'Stanford University', 'Danish Energy Agency',
            'International Energy Agency', 'IRENA', 'Copenhagen Infrastructure Partners'
        ],
        'LOC': [
            'Denmark', 'Copenhagen', 'Brussels', 'Silicon Valley', 'Beijing',
            'Washington', 'London', 'Paris', 'Berlin', 'Tokyo',
            'Bornholm', 'North Sea', 'Baltic Sea', 'Scandinavia',
            'European Union', 'United States', 'China', 'India'
        ],
        'DATE': [
            '2024', '2025', 'January 2025', 'next decade', 'by 2030',
            '2050', 'last year', 'this month', 'Q1 2024', 'December 2023',
            '2020-2030', 'the past five years', 'recent years', 'coming years'
        ]
    }

    @classmethod
    def generate_extracted_nouns(
        cls,
        text: str,
        language: str = 'en',
        top_n: int = 20,
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate realistic noun extraction with TF-IDF scores.

        Follows Zipf's law for word frequency distribution, mimicking
        real NLP extraction patterns.

        Args:
            text: Source text (used for context, not actual extraction)
            language: Language code ('en' or 'da')
            top_n: Number of top nouns to return
            seed: Random seed for reproducibility

        Returns:
            List of noun dictionaries with keys:
                - text: The noun text
                - lemma: Lemmatized form
                - count: Frequency count in document
                - tfidf_score: TF-IDF score (0.0 to 1.0)

        Example:
            >>> text = "Climate change requires urgent climate action..."
            >>> nouns = NLPDataFactory.generate_extracted_nouns(text, 'en', 10, seed=42)
            >>> assert len(nouns) == 10
            >>> assert nouns[0]['tfidf_score'] > nouns[-1]['tfidf_score']
            >>> assert all('text' in n and 'tfidf_score' in n for n in nouns)
        """
        if seed is not None:
            set_seed(seed)

        # Select base vocabulary
        base_vocab = cls.ENGLISH_NOUNS if language == 'en' else cls.DANISH_NOUNS

        # Detect issue type from text and add domain-specific nouns
        domain_nouns = cls._get_domain_nouns(text, language)
        noun_pool = list(set(base_vocab + domain_nouns))

        # Generate nouns with Zipf distribution
        num_nouns = min(top_n, len(noun_pool))
        selected_nouns = random.sample(noun_pool, num_nouns)

        # Generate frequencies following Zipf's law
        frequencies = generate_zipf_distribution(num_nouns, alpha=1.0, seed=seed)
        counts = (frequencies * 1000).astype(int) + 1  # Scale to realistic counts

        # Generate TF-IDF scores
        tfidf_scores = generate_realistic_tfidf_scores(num_nouns, seed=seed)

        # Build noun list
        nouns = []
        for i, noun in enumerate(selected_nouns):
            nouns.append({
                'text': noun,
                'lemma': cls._lemmatize(noun, language),
                'count': int(counts[i]),
                'tfidf_score': round(float(tfidf_scores[i]), 4)
            })

        # Sort by TF-IDF score descending
        nouns.sort(key=lambda x: x['tfidf_score'], reverse=True)

        return nouns

    @classmethod
    def generate_extracted_entities(
        cls,
        text: str,
        num_entities: int = 10,
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate realistic Named Entity Recognition results.

        Args:
            text: Source text (used for context)
            num_entities: Total number of entities to extract
            seed: Random seed for reproducibility

        Returns:
            List of entity dictionaries with keys:
                - text: Entity text
                - type: Entity type (PERSON, ORG, LOC, DATE)
                - count: Frequency in document
                - confidence: Model confidence score (0.7 to 0.99)

        Example:
            >>> text = "Ørsted announced new wind projects in Denmark..."
            >>> entities = NLPDataFactory.generate_extracted_entities(text, 5, seed=42)
            >>> assert len(entities) <= 5
            >>> assert all(e['type'] in ['PERSON', 'ORG', 'LOC', 'DATE'] for e in entities)
        """
        if seed is not None:
            set_seed(seed)

        entities = []
        entity_types = list(cls.ENTITIES.keys())

        # Distribute entities across types
        entities_per_type = num_entities // len(entity_types)
        remaining = num_entities % len(entity_types)

        for entity_type in entity_types:
            num_of_type = entities_per_type + (1 if remaining > 0 else 0)
            remaining -= 1

            # Select entities of this type
            available = cls.ENTITIES[entity_type]
            selected = random.sample(available, min(num_of_type, len(available)))

            for entity_text in selected:
                # Generate realistic count (higher for more important entities)
                count = random.randint(1, 15)

                # Generate confidence score (higher for well-known entities)
                confidence = random.uniform(0.75, 0.99)

                entities.append({
                    'text': entity_text,
                    'type': entity_type,
                    'count': count,
                    'confidence': round(confidence, 3)
                })

        # Sort by count descending (most frequent first)
        entities.sort(key=lambda x: x['count'], reverse=True)

        return entities[:num_entities]

    @classmethod
    def generate_bulk_extractions(
        cls,
        texts: List[str],
        language: str = 'en',
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate NLP extractions for multiple texts efficiently.

        Args:
            texts: List of text documents
            language: Language code
            seed: Random seed for reproducibility

        Returns:
            List of extraction dictionaries, one per text, with keys:
                - nouns: List of extracted nouns
                - entities: List of extracted entities

        Example:
            >>> texts = ["Climate text 1", "Energy text 2", "Policy text 3"]
            >>> extractions = NLPDataFactory.generate_bulk_extractions(texts, 'en')
            >>> assert len(extractions) == 3
            >>> assert all('nouns' in e and 'entities' in e for e in extractions)
        """
        if seed is not None:
            set_seed(seed)

        extractions = []
        for i, text in enumerate(texts):
            text_seed = seed + i if seed is not None else None

            nouns = cls.generate_extracted_nouns(text, language, 20, text_seed)
            entities = cls.generate_extracted_entities(text, 10, text_seed)

            extractions.append({
                'nouns': nouns,
                'entities': entities
            })

        return extractions

    @classmethod
    def generate_entity_cooccurrence(
        cls,
        num_entities: int = 20,
        seed: Optional[int] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate entity co-occurrence matrix.

        Useful for testing entity relationship analysis.

        Args:
            num_entities: Number of entities
            seed: Random seed

        Returns:
            Dictionary mapping entity pairs to co-occurrence scores

        Example:
            >>> cooccur = NLPDataFactory.generate_entity_cooccurrence(10, seed=42)
            >>> assert isinstance(cooccur, dict)
            >>> # Check some entity pairs have scores
            >>> entity_pairs = list(cooccur.keys())
            >>> assert len(entity_pairs) > 0
        """
        if seed is not None:
            set_seed(seed)

        # Select random entities
        all_entities = []
        for entity_list in cls.ENTITIES.values():
            all_entities.extend(entity_list)

        selected_entities = random.sample(all_entities, min(num_entities, len(all_entities)))

        # Generate co-occurrence scores
        cooccurrence = {}
        for i, entity1 in enumerate(selected_entities):
            for entity2 in selected_entities[i+1:]:
                # Higher score for entities of same type
                base_score = random.uniform(0.1, 0.9)

                # Boost if same type
                type1 = cls._get_entity_type(entity1)
                type2 = cls._get_entity_type(entity2)
                if type1 == type2:
                    base_score *= 1.5

                score = min(base_score, 1.0)
                cooccurrence[f"{entity1}|{entity2}"] = round(score, 3)

        return cooccurrence

    @classmethod
    def generate_topic_distribution(
        cls,
        num_topics: int = 5,
        num_terms: int = 10,
        seed: Optional[int] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate LDA-style topic distribution.

        Args:
            num_topics: Number of topics
            num_terms: Terms per topic
            seed: Random seed

        Returns:
            Dictionary mapping topic IDs to term-probability distributions

        Example:
            >>> topics = NLPDataFactory.generate_topic_distribution(3, 5, seed=42)
            >>> assert len(topics) == 3
            >>> for topic_id, terms in topics.items():
            ...     assert len(terms) == 5
        """
        if seed is not None:
            set_seed(seed)

        topics = {}
        all_nouns = cls.ENGLISH_NOUNS + cls.DANISH_NOUNS

        for topic_idx in range(num_topics):
            topic_id = f"topic_{topic_idx}"

            # Select terms for this topic
            selected_terms = random.sample(all_nouns, min(num_terms, len(all_nouns)))

            # Generate probabilities (sum to 1)
            probs = generate_zipf_distribution(len(selected_terms), alpha=1.2, seed=seed + topic_idx)

            topics[topic_id] = {
                term: round(float(prob), 4)
                for term, prob in zip(selected_terms, probs)
            }

        return topics

    @classmethod
    def _get_domain_nouns(cls, text: str, language: str) -> List[str]:
        """
        Get domain-specific nouns based on text content.

        Args:
            text: Text to analyze
            language: Language code

        Returns:
            List of domain-specific nouns
        """
        text_lower = text.lower()
        domain_nouns = []

        # Climate domain
        if any(kw in text_lower for kw in ['climate', 'klima', 'carbon', 'emissions']):
            if language == 'en':
                domain_nouns.extend(['emissions', 'carbon', 'temperature', 'warming'])
            else:
                domain_nouns.extend(['udledning', 'temperatur', 'opvarmning', 'co2'])

        # Energy domain
        if any(kw in text_lower for kw in ['energy', 'energi', 'wind', 'solar', 'vindmølle']):
            if language == 'en':
                domain_nouns.extend(['turbine', 'panel', 'grid', 'storage', 'capacity'])
            else:
                domain_nouns.extend(['vindmølle', 'solcelle', 'elnet', 'kapacitet', 'produktion'])

        # AI domain
        if any(kw in text_lower for kw in ['ai', 'artificial intelligence', 'machine learning']):
            if language == 'en':
                domain_nouns.extend(['algorithm', 'model', 'training', 'neural', 'automation'])
            else:
                domain_nouns.extend(['algoritme', 'model', 'træning', 'automation'])

        return domain_nouns

    @classmethod
    def _lemmatize(cls, noun: str, language: str) -> str:
        """
        Simple lemmatization (remove plural suffix).

        Args:
            noun: Noun to lemmatize
            language: Language code

        Returns:
            Lemmatized form
        """
        if language == 'en':
            # Simple English plural removal
            if noun.endswith('ies'):
                return noun[:-3] + 'y'
            elif noun.endswith('es'):
                return noun[:-2]
            elif noun.endswith('s'):
                return noun[:-1]
        elif language == 'da':
            # Simple Danish plural removal
            if noun.endswith('er'):
                return noun[:-2]
            elif noun.endswith('e'):
                return noun[:-1]

        return noun

    @classmethod
    def _get_entity_type(cls, entity: str) -> str:
        """
        Get entity type for a given entity.

        Args:
            entity: Entity text

        Returns:
            Entity type string
        """
        for entity_type, entity_list in cls.ENTITIES.items():
            if entity in entity_list:
                return entity_type

        return 'UNKNOWN'

    @classmethod
    def generate_sentiment_scores(
        cls,
        num_documents: int = 10,
        seed: Optional[int] = None
    ) -> List[Dict[str, float]]:
        """
        Generate sentiment analysis scores.

        Args:
            num_documents: Number of documents
            seed: Random seed

        Returns:
            List of sentiment dictionaries with positive, negative, neutral scores

        Example:
            >>> sentiments = NLPDataFactory.generate_sentiment_scores(5, seed=42)
            >>> assert len(sentiments) == 5
            >>> for sent in sentiments:
            ...     total = sent['positive'] + sent['negative'] + sent['neutral']
            ...     assert 0.99 <= total <= 1.01  # Sum to ~1
        """
        if seed is not None:
            set_seed(seed)

        sentiments = []
        for _ in range(num_documents):
            # Generate random sentiment distribution
            scores = np.random.dirichlet([1, 1, 1])  # Sum to 1

            sentiments.append({
                'positive': round(float(scores[0]), 3),
                'negative': round(float(scores[1]), 3),
                'neutral': round(float(scores[2]), 3)
            })

        return sentiments
