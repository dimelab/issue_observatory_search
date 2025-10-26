"""NLP model management with caching and thread-safe access."""
import asyncio
import logging
from typing import Optional, Dict
import spacy
from spacy.language import Language

from backend.config import settings

logger = logging.getLogger(__name__)


class NLPModelManager:
    """
    Manages spaCy NLP models with caching and thread-safe access.

    Features:
    - Lazy loading of models on first use
    - In-memory caching to avoid reloading
    - Thread-safe access with asyncio locks
    - Support for multiple languages
    - Model availability checking

    Example:
        >>> manager = NLPModelManager()
        >>> nlp = await manager.get_model("en")
        >>> doc = nlp("This is a test sentence.")
    """

    _instance: Optional["NLPModelManager"] = None
    _models: Dict[str, Language] = {}
    _locks: Dict[str, asyncio.Lock] = {}
    _global_lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "NLPModelManager":
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the model manager."""
        # Initialize locks for each supported language
        for lang in settings.nlp_languages:
            if lang not in self._locks:
                self._locks[lang] = asyncio.Lock()

    @staticmethod
    def _get_model_name(language: str) -> str:
        """
        Get the spaCy model name for a given language.

        Args:
            language: ISO 639-1 language code (e.g., "en", "da")

        Returns:
            Model name string

        Raises:
            ValueError: If language is not supported
        """
        model_map = {
            "en": settings.spacy_model_en,
            "da": settings.spacy_model_da,
        }

        if language not in model_map:
            raise ValueError(
                f"Language '{language}' not supported. "
                f"Supported languages: {', '.join(model_map.keys())}"
            )

        return model_map[language]

    async def is_model_available(self, language: str) -> bool:
        """
        Check if a spaCy model is installed for the given language.

        Args:
            language: ISO 639-1 language code

        Returns:
            True if model is installed, False otherwise
        """
        try:
            model_name = self._get_model_name(language)
            # Try to load the model in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, spacy.util.get_installed_models)
            return model_name in spacy.util.get_installed_models()
        except (ValueError, OSError):
            return False

    async def get_model(self, language: str) -> Language:
        """
        Get a cached spaCy model or load it if not available.

        This method is thread-safe and will only load each model once.
        Subsequent calls for the same language return the cached model.

        Args:
            language: ISO 639-1 language code (e.g., "en", "da")

        Returns:
            Loaded spaCy Language model

        Raises:
            ValueError: If language is not supported
            RuntimeError: If model is not installed
        """
        # Check if model is already cached
        if language in self._models:
            logger.debug(f"Returning cached spaCy model for language: {language}")
            return self._models[language]

        # Get language-specific lock
        if language not in self._locks:
            async with self._global_lock:
                if language not in self._locks:
                    self._locks[language] = asyncio.Lock()

        # Load model with lock to prevent duplicate loading
        async with self._locks[language]:
            # Double-check after acquiring lock
            if language in self._models:
                return self._models[language]

            model_name = self._get_model_name(language)

            logger.info(f"Loading spaCy model '{model_name}' for language: {language}")

            try:
                # Load model in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                nlp = await loop.run_in_executor(None, spacy.load, model_name)

                # Disable unnecessary pipeline components for performance
                # Keep only: tok2vec, tagger, parser, ner, attribute_ruler, lemmatizer
                disabled_pipes = ["textcat", "textcat_multilabel", "entity_linker"]
                for pipe in disabled_pipes:
                    if nlp.has_pipe(pipe):
                        nlp.remove_pipe(pipe)

                # Cache the model
                self._models[language] = nlp

                logger.info(
                    f"Successfully loaded spaCy model '{model_name}' "
                    f"with components: {nlp.pipe_names}"
                )

                return nlp

            except OSError as e:
                logger.error(
                    f"Failed to load spaCy model '{model_name}'. "
                    f"Please install it with: python -m spacy download {model_name}"
                )
                raise RuntimeError(
                    f"spaCy model '{model_name}' is not installed. "
                    f"Install it with: python -m spacy download {model_name}"
                ) from e

    async def clear_cache(self, language: Optional[str] = None):
        """
        Clear cached models to free memory.

        Args:
            language: If provided, clear only this language's model.
                     If None, clear all cached models.
        """
        async with self._global_lock:
            if language:
                if language in self._models:
                    logger.info(f"Clearing cached model for language: {language}")
                    del self._models[language]
            else:
                logger.info("Clearing all cached NLP models")
                self._models.clear()

    def get_cached_languages(self) -> list[str]:
        """
        Get list of languages with currently cached models.

        Returns:
            List of language codes
        """
        return list(self._models.keys())

    def get_cache_size(self) -> int:
        """
        Get number of cached models.

        Returns:
            Number of models in cache
        """
        return len(self._models)


# Global instance for easy access
nlp_model_manager = NLPModelManager()
