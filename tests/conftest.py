"""Pytest configuration and fixtures."""
import asyncio
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.config import settings
from backend.database import Base, get_db
from backend.main import app
from backend.models.user import User
from backend.utils.auth import get_password_hash


# Test database URL (using port 5433 to match docker-compose configuration)
TEST_DATABASE_URL = "postgresql+psycopg://test:test@localhost:5433/test_issue_observatory"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """Create async engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test with transaction rollback."""
    connection = await engine.connect()
    transaction = await connection.begin()

    async_session = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await transaction.rollback()
    await connection.close()


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    """Create a test client with overridden database dependency."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
        is_admin=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create a test admin user."""
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=get_password_hash("adminpass123"),
        is_admin=True,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client: TestClient, test_user: User) -> dict:
    """Get authentication headers for a test user."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient, test_admin: User) -> dict:
    """Get authentication headers for an admin user."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "adminpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# Synthetic data fixtures
@pytest.fixture
def synthetic_search_results():
    """Generate synthetic search results for testing."""
    from tests.factories import SearchResultFactory

    return SearchResultFactory.create_search_results(
        query="climate change",
        num_results=10,
        language='en',
        seed=42
    )


@pytest.fixture
def synthetic_search_results_bulk():
    """Generate synthetic search results for multiple queries."""
    from tests.factories import SearchResultFactory

    queries = [
        "climate change mitigation",
        "renewable energy policy",
        "carbon emissions tracking"
    ]

    return SearchResultFactory.create_bulk_results(
        queries=queries,
        results_per_query=10,
        language='en',
        seed=42
    )


@pytest.fixture
def synthetic_website_content():
    """Generate synthetic website content for testing."""
    from tests.factories import WebsiteContentFactory

    return WebsiteContentFactory.create_website_content(
        url="https://example.com/climate-article",
        issue_type='climate',
        depth=1,
        seed=42
    )


@pytest.fixture
def synthetic_website_content_with_depth():
    """Generate synthetic website content with linked pages."""
    from tests.factories import WebsiteContentFactory

    return WebsiteContentFactory.create_website_content(
        url="https://example.com/climate-article",
        issue_type='climate',
        depth=2,
        seed=42
    )


@pytest.fixture
def synthetic_bulk_content():
    """Generate synthetic content for multiple URLs."""
    from tests.factories import WebsiteContentFactory

    urls = [
        "https://nature.com/climate-study",
        "https://bbc.co.uk/news/climate",
        "https://greenpeace.org/climate-action",
        "https://example.com/blog/climate"
    ]

    return WebsiteContentFactory.create_bulk_content(
        urls=urls,
        issue_type='climate',
        seed=42
    )


@pytest.fixture
def synthetic_nlp_data():
    """Generate synthetic NLP extraction data."""
    from tests.factories import NLPDataFactory

    text = """
    Climate change represents one of the most significant challenges facing
    humanity. The scientific consensus, backed by organizations like the IPCC,
    indicates that global warming is caused by human activities. Renewable energy
    solutions and carbon reduction strategies are essential for mitigation.
    """

    return {
        'nouns': NLPDataFactory.generate_extracted_nouns(
            text, language='en', top_n=20, seed=42
        ),
        'entities': NLPDataFactory.generate_extracted_entities(
            text, num_entities=10, seed=42
        )
    }


@pytest.fixture
def synthetic_nlp_bulk():
    """Generate NLP extractions for multiple texts."""
    from tests.factories import NLPDataFactory

    texts = [
        "Climate change and renewable energy solutions...",
        "Artificial intelligence ethics and governance...",
        "Danish wind energy development in the North Sea..."
    ]

    return NLPDataFactory.generate_bulk_extractions(
        texts=texts,
        language='en',
        seed=42
    )


@pytest.fixture
def synthetic_network():
    """Generate synthetic issue-website network."""
    from tests.factories import NetworkDataFactory

    return NetworkDataFactory.create_issue_website_network(
        num_queries=5,
        num_websites=50,
        seed=42
    )


@pytest.fixture
def synthetic_website_noun_network():
    """Generate synthetic website-noun bipartite network."""
    from tests.factories import NetworkDataFactory

    return NetworkDataFactory.create_website_noun_network(
        num_websites=30,
        num_nouns=100,
        seed=42
    )


@pytest.fixture
def synthetic_concept_network():
    """Generate synthetic website-concept knowledge graph."""
    from tests.factories import NetworkDataFactory

    return NetworkDataFactory.create_website_concept_network(
        num_websites=25,
        num_concepts=15,
        seed=42
    )


@pytest.fixture
def large_synthetic_dataset():
    """
    Generate large synthetic dataset for performance testing.

    Returns dictionary with:
        - search_results: 100 queries x 30 results = 3000 results
        - website_content: 100 websites with content
        - nlp_extractions: NLP data for 100 documents
        - network: Large network with 1000+ nodes
    """
    from tests.factories import (
        SearchResultFactory,
        WebsiteContentFactory,
        NLPDataFactory,
        NetworkDataFactory
    )

    # Generate 100 queries
    queries = [f"test query {i}" for i in range(100)]

    # Generate search results
    search_results = SearchResultFactory.create_bulk_results(
        queries=queries,
        results_per_query=30,
        language='en',
        seed=42
    )

    # Generate website content for first 100 URLs
    all_urls = []
    for query_results in search_results.values():
        all_urls.extend([r['url'] for r in query_results[:1]])  # 1 per query = 100 total

    website_content = WebsiteContentFactory.create_bulk_content(
        urls=all_urls[:100],
        issue_type='climate',
        seed=42
    )

    # Generate NLP extractions
    texts = [content['text'] for content in website_content]
    nlp_extractions = NLPDataFactory.generate_bulk_extractions(
        texts=texts,
        language='en',
        seed=42
    )

    # Generate large network
    network = NetworkDataFactory.create_large_scale_network(
        size='medium',  # ~1000 nodes
        seed=42
    )

    return {
        'search_results': search_results,
        'website_content': website_content,
        'nlp_extractions': nlp_extractions,
        'network': network
    }
