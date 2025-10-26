"""
Base utilities for synthetic data generation.

Provides shared utilities for all factory classes including:
- Random seed management for reproducibility
- Statistical distributions (Zipf's law, Power law)
- Issue-specific vocabularies
- Language detection
"""
from typing import Dict, List, Optional
import numpy as np
import random


def set_seed(seed: Optional[int] = None) -> None:
    """
    Set random seed for reproducibility across all random generators.

    Args:
        seed: Random seed value. If None, does not set seed.

    Example:
        >>> set_seed(42)
        >>> values = generate_zipf_distribution(10)
        >>> # Same seed will always produce same values
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)


def generate_zipf_distribution(n: int, alpha: float = 1.0, seed: Optional[int] = None) -> np.ndarray:
    """
    Generate values following Zipf's law distribution.

    Zipf's law states that the frequency of items is inversely proportional
    to their rank. This is realistic for word frequencies, noun counts, etc.

    Args:
        n: Number of values to generate
        alpha: Distribution parameter (default 1.0). Higher values = steeper curve
        seed: Random seed for reproducibility

    Returns:
        Array of n values following Zipf distribution, normalized to sum to 1.0

    Example:
        >>> freqs = generate_zipf_distribution(10, alpha=1.0)
        >>> # freqs[0] will be highest, following power law decay
        >>> assert freqs[0] > freqs[1] > freqs[2]
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate Zipf distribution: frequency ~ 1/rank^alpha
    ranks = np.arange(1, n + 1)
    frequencies = 1.0 / (ranks ** alpha)

    # Normalize to sum to 1
    frequencies = frequencies / frequencies.sum()

    return frequencies


def generate_power_law_distribution(
    n: int,
    gamma: float = 2.0,
    seed: Optional[int] = None
) -> np.ndarray:
    """
    Generate values following power law distribution.

    Power law distributions are common in network degree distributions,
    where P(k) ~ k^(-gamma).

    Args:
        n: Number of values to generate
        gamma: Power law exponent (default 2.0). Typical range 2-3 for real networks
        seed: Random seed for reproducibility

    Returns:
        Array of n integer values following power law distribution

    Example:
        >>> degrees = generate_power_law_distribution(100, gamma=2.5)
        >>> # Most nodes have low degree, few have high degree
        >>> assert np.median(degrees) < np.mean(degrees)  # Right-skewed
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate power law: P(k) ~ k^(-gamma)
    # Use inverse transform sampling
    u = np.random.uniform(0, 1, n)
    k_min = 1
    k_max = 100

    # Power law inverse CDF
    values = k_min * ((k_max / k_min) ** u) ** (1 / (1 - gamma))

    return np.round(values).astype(int)


def get_issue_vocabulary(issue_type: str) -> Dict[str, List[str]]:
    """
    Get issue-specific vocabulary for different research topics.

    Args:
        issue_type: Type of issue ('climate', 'ai', 'renewable_energy', etc.)

    Returns:
        Dictionary with keys: 'keywords', 'entities', 'verbs', 'adjectives'

    Example:
        >>> vocab = get_issue_vocabulary('climate')
        >>> assert 'carbon' in vocab['keywords']
        >>> assert 'IPCC' in vocab['entities']
    """
    vocabularies = {
        'climate': {
            'keywords': [
                'climate', 'warming', 'carbon', 'emissions', 'greenhouse', 'temperature',
                'fossil', 'renewable', 'sustainability', 'mitigation', 'adaptation',
                'IPCC', 'Paris Agreement', 'net-zero', 'decarbonization', 'climate change'
            ],
            'entities': [
                'IPCC', 'Paris Agreement', 'COP28', 'UN Climate Summit',
                'Greta Thunberg', 'Bill McKibben', 'Michael Mann',
                'Greenpeace', 'WWF', '350.org', 'Climate Action Network'
            ],
            'verbs': [
                'reduce', 'mitigate', 'adapt', 'transition', 'decarbonize',
                'emit', 'sequester', 'offset', 'pollute', 'conserve'
            ],
            'adjectives': [
                'sustainable', 'renewable', 'clean', 'green', 'carbon-neutral',
                'catastrophic', 'urgent', 'irreversible', 'unprecedented'
            ]
        },
        'ai': {
            'keywords': [
                'artificial intelligence', 'machine learning', 'neural network', 'algorithm',
                'automation', 'deep learning', 'GPT', 'LLM', 'AGI', 'training',
                'model', 'dataset', 'bias', 'ethics', 'safety', 'alignment'
            ],
            'entities': [
                'OpenAI', 'Google DeepMind', 'Anthropic', 'Meta AI',
                'Geoffrey Hinton', 'Yann LeCun', 'Andrew Ng', 'Sam Altman',
                'MIT CSAIL', 'Stanford AI Lab', 'Berkeley BAIR'
            ],
            'verbs': [
                'train', 'fine-tune', 'deploy', 'optimize', 'predict',
                'classify', 'generate', 'automate', 'learn', 'infer'
            ],
            'adjectives': [
                'intelligent', 'autonomous', 'neural', 'algorithmic', 'predictive',
                'biased', 'explainable', 'transparent', 'black-box', 'cutting-edge'
            ]
        },
        'renewable_energy': {
            'keywords': [
                'wind', 'solar', 'renewable', 'turbine', 'panel', 'battery',
                'grid', 'storage', 'offshore', 'onshore', 'capacity',
                'efficiency', 'investment', 'subsidy', 'intermittency'
            ],
            'entities': [
                'Ørsted', 'Vestas', 'Siemens Gamesa', 'Danish Energy Agency',
                'DONG Energy', 'European Wind Energy Association',
                'International Renewable Energy Agency', 'IRENA'
            ],
            'verbs': [
                'generate', 'install', 'operate', 'maintain', 'invest',
                'deploy', 'scale', 'integrate', 'store', 'transmit'
            ],
            'adjectives': [
                'renewable', 'clean', 'sustainable', 'offshore', 'onshore',
                'efficient', 'cost-effective', 'intermittent', 'baseload'
            ]
        },
        'renewable_energy_denmark': {
            'keywords': [
                'vindmøller', 'solenergi', 'grøn energi', 'vedvarende energi',
                'havvind', 'landvind', 'energiø', 'bornholm',
                'vindmøllepark', 'solceller', 'energilagring', 'elnet'
            ],
            'entities': [
                'Ørsted', 'Vestas', 'Energistyrelsen', 'Energinet',
                'Copenhagen Infrastructure Partners', 'Better Energy',
                'European Energy', 'Ørsted A/S'
            ],
            'verbs': [
                'producere', 'installere', 'udvikle', 'investere', 'udbygge',
                'driftsætte', 'integrere', 'eksportere', 'lagre'
            ],
            'adjectives': [
                'vedvarende', 'grøn', 'bæredygtig', 'fossil-fri', 'klimavenlig',
                'effektiv', 'omkostningseffektiv', 'skalérbar'
            ]
        }
    }

    # Return vocabulary or default to climate if not found
    return vocabularies.get(issue_type, vocabularies['climate'])


def detect_language(text: str) -> str:
    """
    Simple language detection based on common words.

    Args:
        text: Text to analyze

    Returns:
        Language code ('da' for Danish, 'en' for English)

    Example:
        >>> detect_language("Dette er dansk tekst")
        'da'
        >>> detect_language("This is English text")
        'en'
    """
    # Common Danish words
    danish_indicators = [
        'og', 'er', 'det', 'en', 'til', 'med', 'som', 'på', 'af',
        'vindmøller', 'energi', 'denmark', 'dansk', 'københavn',
        'være', 'også', 'hvor', 'over', 'efter'
    ]

    text_lower = text.lower()
    danish_count = sum(1 for word in danish_indicators if word in text_lower)

    # If more than 2 Danish indicators, consider it Danish
    return 'da' if danish_count >= 2 else 'en'


def generate_realistic_tfidf_scores(
    n: int,
    seed: Optional[int] = None
) -> List[float]:
    """
    Generate realistic TF-IDF scores following power law distribution.

    Args:
        n: Number of scores to generate
        seed: Random seed for reproducibility

    Returns:
        List of n TF-IDF scores in descending order

    Example:
        >>> scores = generate_realistic_tfidf_scores(10, seed=42)
        >>> assert scores[0] > scores[-1]  # Descending order
        >>> assert all(0 <= s <= 1.0 for s in scores)  # Valid range
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate base scores following power law
    base_scores = generate_zipf_distribution(n, alpha=1.2, seed=seed)

    # Scale to realistic TF-IDF range (0.1 to 0.95)
    scores = 0.1 + (base_scores / base_scores.max()) * 0.85

    # Sort descending
    scores = np.sort(scores)[::-1]

    return scores.tolist()


def weighted_choice(choices: Dict[str, float], seed: Optional[int] = None) -> str:
    """
    Make a weighted random choice from a dictionary.

    Args:
        choices: Dictionary mapping choices to weights
        seed: Random seed for reproducibility

    Returns:
        Selected choice based on weights

    Example:
        >>> choices = {'a': 0.7, 'b': 0.2, 'c': 0.1}
        >>> result = weighted_choice(choices, seed=42)
        >>> assert result in ['a', 'b', 'c']
    """
    if seed is not None:
        np.random.seed(seed)

    items = list(choices.keys())
    weights = list(choices.values())

    # Normalize weights
    total = sum(weights)
    weights = [w / total for w in weights]

    return np.random.choice(items, p=weights)


def generate_zipf_frequencies(vocabulary: List[str], seed: Optional[int] = None) -> Dict[str, int]:
    """
    Assign Zipf-distributed frequencies to vocabulary items.

    Args:
        vocabulary: List of terms
        seed: Random seed for reproducibility

    Returns:
        Dictionary mapping terms to frequencies

    Example:
        >>> vocab = ['climate', 'energy', 'policy']
        >>> freqs = generate_zipf_frequencies(vocab, seed=42)
        >>> # First term should have highest frequency
        >>> assert freqs['climate'] >= freqs['energy']
    """
    n = len(vocabulary)
    frequencies = generate_zipf_distribution(n, alpha=1.0, seed=seed)

    # Scale to realistic counts (10 to 1000)
    counts = (frequencies * 990 + 10).astype(int)

    return dict(zip(vocabulary, counts))
