# Testing Quick Start

Quick reference for running tests in Issue Observatory Search.

## Setup (One-Time)

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Setup test database
bash scripts/setup_test_db.sh

# 3. Verify setup
pytest --version
```

## Common Test Commands

```bash
# Run all tests with coverage
pytest --cov=backend --cov-report=term-missing

# Run specific test file
pytest tests/test_auth.py -v

# Run tests in parallel (faster)
pytest -n auto -v

# Run with detailed output
pytest -vv

# Stop on first failure
pytest -x

# Re-run only failed tests
pytest --lf
```

## Quick Tests by Feature

```bash
# Authentication
pytest tests/test_auth.py -v

# Search functionality
pytest tests/test_search_endpoints.py -v
pytest tests/test_search_engines.py -v

# Web scraping
pytest tests/test_scraping.py -v

# Security
pytest tests/test_security.py -v

# Admin features
pytest tests/test_admin.py -v

# Performance
pytest tests/test_performance.py -v

# Synthetic data performance
pytest tests/test_synthetic_performance.py -v -s
```

## Coverage Reports

```bash
# Terminal report
pytest --cov=backend --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=backend --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Debugging

```bash
# Show print statements
pytest -v -s

# Drop into debugger on failure
pytest --pdb -x

# Detailed traceback
pytest -v --tb=long

# Run specific test function
pytest tests/test_auth.py::test_login_success -v
```

## Test Database Issues?

```bash
# Reset test database
bash scripts/setup_test_db.sh

# Or manually:
docker exec -it <container> dropdb -U postgres test_issue_observatory
docker exec -it <container> createdb -U postgres test_issue_observatory
```

## Expected Results

- ✅ 200+ tests
- ✅ 80%+ coverage
- ✅ All passing (some may skip if no API keys)

📖 **[Full Testing Guide](TESTING_GUIDE.md)** for detailed documentation
