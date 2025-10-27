# Testing Guide

This guide will help you run the comprehensive test suite for Issue Observatory Search.

## Prerequisites

1. **Activate virtual environment** (REQUIRED):
   ```bash
   source .venv/bin/activate
   # You should see (.venv) in your prompt
   ```

2. **Install dependencies** (if not done already):
   ```bash
   pip install -e .[dev]
   ```

3. **Setup test database**:
   The tests use a separate test database to avoid affecting your development data.

   ```bash
   # Create test database (only needed once)
   docker-compose up -d postgres

   # Create the test database
   docker exec -it issue_observatory_search-postgres-1 psql -U postgres -c "CREATE DATABASE test_issue_observatory;"
   docker exec -it issue_observatory_search-postgres-1 psql -U postgres -c "CREATE USER test WITH PASSWORD 'test';"
   docker exec -it issue_observatory_search-postgres-1 psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE test_issue_observatory TO test;"
   ```

## Test Structure

The project has comprehensive test coverage organized as follows:

```
tests/
├── conftest.py                    # Pytest configuration and fixtures
├── test_auth.py                   # Authentication tests
├── test_admin.py                  # Admin API tests
├── test_search_endpoints.py       # Search API tests
├── test_search_engines.py         # Search engine integration tests
├── test_serper_search.py          # Serper API tests
├── test_scraping.py               # Web scraping tests
├── test_security.py               # Security vulnerability tests
├── test_monitoring.py             # Monitoring and health check tests
├── test_performance.py            # Performance tests
├── test_synthetic_performance.py  # Large-scale performance tests with synthetic data
├── factories/                     # Synthetic data factories
│   ├── search_factory.py          # Generate fake search results
│   ├── content_factory.py         # Generate fake website content
│   ├── nlp_factory.py             # Generate fake NLP data
│   └── network_factory.py         # Generate fake network data
├── unit/                          # Unit tests
└── integration/                   # Integration tests
```

## Running Tests

### 1. Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run with detailed output for each test
pytest -vv
```

### 2. Run Specific Test Files

```bash
# Test authentication
pytest tests/test_auth.py -v

# Test search functionality
pytest tests/test_search_endpoints.py -v

# Test web scraping
pytest tests/test_scraping.py -v

# Test security
pytest tests/test_security.py -v

# Test performance
pytest tests/test_performance.py -v
```

### 3. Run Tests by Pattern

```bash
# Run all tests with "auth" in the name
pytest -k auth -v

# Run all tests with "search" in the name
pytest -k search -v

# Run all tests that DON'T contain "slow"
pytest -k "not slow" -v
```

### 4. Run Tests in Parallel

The project uses `pytest-xdist` for parallel test execution:

```bash
# Run tests in parallel using all CPU cores
pytest -n auto

# Run tests using 4 workers
pytest -n 4

# Parallel with verbose output
pytest -n auto -v
```

### 5. Coverage Reports

```bash
# Run tests with coverage report
pytest --cov=backend --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=backend --cov-report=html

# View HTML report
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### 6. Run Specific Test Functions

```bash
# Run a specific test function
pytest tests/test_auth.py::test_login_success -v

# Run all tests in a class
pytest tests/test_admin.py::TestAdminAPI -v

# Run multiple specific tests
pytest tests/test_auth.py::test_login_success tests/test_auth.py::test_login_invalid -v
```

## Test Categories

### Unit Tests

Fast, isolated tests for individual functions and classes:

```bash
pytest tests/unit/ -v
```

### Integration Tests

Tests that verify multiple components work together:

```bash
pytest tests/integration/ -v
```

### Performance Tests

Tests that verify performance meets requirements:

```bash
# Basic performance tests
pytest tests/test_performance.py -v

# Large-scale synthetic data performance tests
pytest tests/test_synthetic_performance.py -v -s
```

### Security Tests

Tests that verify security vulnerabilities are mitigated:

```bash
pytest tests/test_security.py -v
```

## Fixtures Available

The test suite provides many fixtures (see `tests/conftest.py`):

### Database Fixtures
- `db_session` - Clean database session for each test
- `engine` - Async database engine

### User Fixtures
- `test_user` - Regular test user
- `test_admin` - Admin test user
- `auth_headers` - Authorization headers for test user
- `admin_headers` - Authorization headers for admin user

### Synthetic Data Fixtures
- `synthetic_search_results` - 10 fake search results
- `synthetic_search_results_bulk` - Bulk search results for 3 queries
- `synthetic_website_content` - Single fake website content
- `synthetic_website_content_with_depth` - Website content with linked pages
- `synthetic_bulk_content` - Multiple fake website contents
- `synthetic_nlp_data` - Fake NLP extraction data
- `synthetic_nlp_bulk` - Bulk NLP extractions
- `synthetic_network` - Fake issue-website network
- `synthetic_website_noun_network` - Fake website-noun network
- `synthetic_concept_network` - Fake website-concept network
- `large_synthetic_dataset` - Large dataset for performance testing (3000+ items)

### Example Test Using Fixtures

```python
import pytest
from fastapi.testclient import TestClient

def test_get_user_profile(client: TestClient, auth_headers: dict, test_user):
    """Test getting user profile with authentication."""
    response = client.get("/api/user/profile", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
```

## Common Testing Scenarios

### Testing Authentication

```bash
# Run all auth tests
pytest tests/test_auth.py -v

# Test login
pytest tests/test_auth.py::test_login_success -v

# Test token validation
pytest tests/test_auth.py::test_token_validation -v
```

### Testing Search Functionality

```bash
# Test search endpoints
pytest tests/test_search_endpoints.py -v

# Test specific search engine
pytest tests/test_search_engines.py::test_google_search -v

# Test Serper integration
pytest tests/test_serper_search.py -v
```

### Testing Web Scraping

```bash
# Test scraping functionality
pytest tests/test_scraping.py -v

# Test robots.txt compliance
pytest tests/test_scraping.py::test_robots_txt_compliance -v

# Test multi-level scraping
pytest tests/test_scraping.py::test_multi_level_scraping -v
```

### Testing with Synthetic Data

```bash
# Test with synthetic data
pytest tests/test_synthetic_performance.py -v

# Show synthetic data output (use -s to show prints)
pytest tests/test_synthetic_performance.py -v -s
```

## Debugging Failed Tests

### 1. Show Print Statements

```bash
# Show print() output even for passing tests
pytest -v -s

# Show output only for failed tests
pytest -v
```

### 2. Stop on First Failure

```bash
# Stop after first failure
pytest -x

# Stop after 3 failures
pytest --maxfail=3
```

### 3. Run Last Failed Tests

```bash
# Re-run only tests that failed last time
pytest --lf

# Re-run failed tests first, then remaining tests
pytest --ff
```

### 4. Detailed Traceback

```bash
# Show detailed traceback
pytest -v --tb=long

# Show short traceback
pytest -v --tb=short

# Show only one line per failure
pytest -v --tb=line
```

### 5. Drop into Debugger on Failure

```bash
# Start Python debugger on failure
pytest --pdb

# Start Python debugger on first failure
pytest --pdb -x
```

## Continuous Integration

The project is configured to run tests automatically on every commit. The CI/CD pipeline runs:

1. **Linting**: `flake8` and `black --check`
2. **Type checking**: `mypy`
3. **Security checks**: `bandit` and `safety`
4. **Tests**: `pytest` with coverage
5. **Coverage threshold**: Requires 80%+ code coverage

## Troubleshooting

### Test Database Connection Issues

If tests fail with database connection errors:

```bash
# Check if PostgreSQL container is running
docker ps | grep postgres

# Restart PostgreSQL container
docker-compose restart postgres

# Recreate test database
docker exec -it issue_observatory_search-postgres-1 dropdb -U postgres test_issue_observatory --if-exists
docker exec -it issue_observatory_search-postgres-1 createdb -U postgres test_issue_observatory
```

### Import Errors

If you see "ModuleNotFoundError":

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall package in development mode
pip install -e .[dev]

# Verify installation
python -c "from backend.main import app; print('Success')"
```

### Slow Tests

Some tests (especially scraping and performance tests) may be slow:

```bash
# Skip slow tests
pytest -m "not slow" -v

# Run only fast tests
pytest -k "not performance and not scraping" -v

# Run with parallel execution
pytest -n auto -v
```

## Writing New Tests

### Basic Test Template

```python
import pytest
from fastapi.testclient import TestClient

def test_my_feature(client: TestClient, auth_headers: dict):
    """Test description here."""
    # Arrange - set up test data
    data = {"key": "value"}

    # Act - perform the action
    response = client.post("/api/endpoint", json=data, headers=auth_headers)

    # Assert - verify the result
    assert response.status_code == 200
    assert response.json()["success"] is True
```

### Async Test Template

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_my_async_feature(db_session: AsyncSession):
    """Test async functionality."""
    # Your async test code here
    result = await some_async_function()
    assert result is not None
```

### Parametrized Test Template

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("test1", "result1"),
    ("test2", "result2"),
    ("test3", "result3"),
])
def test_multiple_inputs(input: str, expected: str):
    """Test with multiple parameter combinations."""
    result = my_function(input)
    assert result == expected
```

## Test Markers

The project uses pytest markers to categorize tests:

```python
@pytest.mark.slow  # Slow-running test
@pytest.mark.integration  # Integration test
@pytest.mark.unit  # Unit test
@pytest.mark.asyncio  # Async test
```

Run tests by marker:

```bash
# Run only slow tests
pytest -m slow -v

# Run only integration tests
pytest -m integration -v

# Run everything except slow tests
pytest -m "not slow" -v
```

## Expected Test Results

The test suite should have:
- ✅ **~50+ test files**
- ✅ **~200+ test functions**
- ✅ **80%+ code coverage**
- ✅ **All tests passing** (some may be skipped if API keys not configured)

## Next Steps

1. **Run basic tests**:
   ```bash
   pytest tests/test_auth.py -v
   ```

2. **Run with coverage**:
   ```bash
   pytest --cov=backend --cov-report=term-missing
   ```

3. **Check failing tests**:
   - Review test output
   - Fix any issues in the code
   - Re-run tests

4. **Add new tests** as you develop new features

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
