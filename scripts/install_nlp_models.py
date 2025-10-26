#!/usr/bin/env python3
"""Install spaCy NLP models required for content analysis."""
import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Models to install
MODELS = [
    {
        "name": "en_core_web_sm",
        "language": "English",
        "description": "English core model (small)",
        "size": "~13 MB"
    },
    {
        "name": "da_core_news_sm",
        "language": "Danish",
        "description": "Danish core model (small)",
        "size": "~13 MB"
    },
]


def check_model_installed(model_name: str) -> bool:
    """
    Check if a spaCy model is already installed.

    Args:
        model_name: Name of the model to check

    Returns:
        True if installed, False otherwise
    """
    try:
        import spacy
        spacy.load(model_name)
        return True
    except (OSError, ImportError):
        return False


def install_model(model_name: str) -> bool:
    """
    Install a spaCy model.

    Args:
        model_name: Name of the model to install

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Installing {model_name}...")

        # Run spaCy download command
        result = subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            logger.info(f"✓ Successfully installed {model_name}")
            return True
        else:
            logger.error(f"✗ Failed to install {model_name}")
            logger.error(f"Error: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"✗ Error installing {model_name}: {e}")
        return False


def main():
    """Install all required spaCy models."""
    logger.info("=" * 60)
    logger.info("Installing spaCy NLP Models")
    logger.info("=" * 60)
    logger.info("")

    # Check if spaCy is installed
    try:
        import spacy
        logger.info(f"spaCy version: {spacy.__version__}")
    except ImportError:
        logger.error("spaCy is not installed. Please install it first:")
        logger.error("  pip install spacy>=3.7.0")
        sys.exit(1)

    logger.info("")
    logger.info("Models to install:")
    for model in MODELS:
        logger.info(f"  - {model['name']} ({model['language']}) - {model['size']}")
    logger.info("")

    # Install each model
    results = []
    for model in MODELS:
        model_name = model["name"]
        language = model["language"]

        logger.info(f"Checking {language} model ({model_name})...")

        if check_model_installed(model_name):
            logger.info(f"✓ {model_name} is already installed")
            results.append((model_name, True, "already_installed"))
        else:
            success = install_model(model_name)
            results.append((model_name, success, "installed" if success else "failed"))

        logger.info("")

    # Print summary
    logger.info("=" * 60)
    logger.info("Installation Summary")
    logger.info("=" * 60)

    successful = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)

    for model_name, success, status in results:
        status_icon = "✓" if success else "✗"
        logger.info(f"{status_icon} {model_name}: {status}")

    logger.info("")
    logger.info(f"Total: {successful} successful, {failed} failed")

    if failed > 0:
        logger.error("")
        logger.error("Some models failed to install. Please install them manually:")
        for model_name, success, _ in results:
            if not success:
                logger.error(f"  python -m spacy download {model_name}")
        sys.exit(1)
    else:
        logger.info("")
        logger.info("All models installed successfully!")
        logger.info("You can now use the content analysis features.")
        sys.exit(0)


if __name__ == "__main__":
    main()
