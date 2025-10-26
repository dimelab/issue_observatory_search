"""Setup configuration for Issue Observatory Search."""
from setuptools import setup, find_packages
from pathlib import Path

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read dependencies from requirements.txt
def read_requirements(filename):
    """Read requirements from a file, ignoring comments and blank lines."""
    req_path = Path(__file__).parent / filename
    if not req_path.exists():
        return []

    requirements = []
    with open(req_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments, blank lines
            if not line or line.startswith('#'):
                continue

            # Remove inline comments
            if '#' in line:
                line = line.split('#')[0].strip()

            # Skip empty lines after comment removal
            if line:
                requirements.append(line)

    return requirements

# Core dependencies (from requirements.txt)
install_requires = read_requirements('requirements.txt')

# Development dependencies (from requirements-dev.txt if it exists, or hardcoded)
dev_requires = [
    "pytest>=7.4.3,<8.0.0",
    "pytest-asyncio>=0.21.1,<1.0.0",
    "pytest-cov>=4.1.0,<5.0.0",
    "pytest-mock>=3.12.0",
    "pytest-xdist>=3.5.0",
    "black>=23.11.0,<25.0.0",
    "ruff>=0.1.6,<1.0.0",
    "isort>=5.13.0,<6.0.0",
    "mypy>=1.7.1,<2.0.0",
    "flake8>=7.0.0,<8.0.0",
    "bandit>=1.7.6",
    "safety>=3.0.0",
    "pre-commit>=3.6.0",
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
