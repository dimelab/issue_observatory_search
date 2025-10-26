"""Setup configuration for Issue Observatory Search."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Core dependencies
install_requires = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy[asyncio]>=2.0.23",
    "psycopg[binary]>=3.1.0",
    "alembic>=1.12.1",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "redis>=5.0.1",
    "celery>=5.3.4",
    "httpx>=0.25.2",
    "playwright>=1.40.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=4.9.0",
    "langdetect>=1.0.9",
    # NLP dependencies
    "spacy>=3.7.0",
    "scikit-learn>=1.3.0",
    "numpy>=1.24.0",
    # Network analysis dependencies
    "networkx>=3.0",
    "python-louvain>=0.16",  # Community detection
]

# Development dependencies
dev_requires = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "black>=23.11.0",
    "ruff>=0.1.6",
    "mypy>=1.7.1",
]

setup(
    name="issue-observatory-search",
    version="5.0.0",
    author="Issue Observatory Team",
    description="Web application for mapping issues through web searches and content analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/issue-observatory-search",
    packages=find_packages(include=["backend", "backend.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    python_requires=">=3.11",
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
    },
    entry_points={
        "console_scripts": [
            "issue-observatory=backend.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
