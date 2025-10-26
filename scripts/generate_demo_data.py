#!/usr/bin/env python3
"""
Generate synthetic demo data for Issue Observatory Search.

This script creates a comprehensive demo dataset including:
- Demo user account
- Multiple research topics (Danish renewable energy, AI ethics, Climate change)
- Search results for each topic
- Scraped website content
- NLP extractions (nouns and entities)
- All network types (issue-website, website-noun, website-concept)

Usage:
    python scripts/generate_demo_data.py
    python scripts/generate_demo_data.py --num-topics 5 --results-per-query 50
"""
import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from backend.config import settings
from backend.database import Base
from backend.models.user import User
from backend.models.search import SearchSession, SearchQuery, SearchResult
from backend.models.website import WebsiteContent
from backend.models.analysis import ExtractedNoun, ExtractedEntity
from backend.models.network import NetworkExport
from backend.utils.auth import get_password_hash

from tests.factories import (
    SearchResultFactory,
    WebsiteContentFactory,
    NLPDataFactory,
    NetworkDataFactory
)


# Demo research topics configuration
DEMO_TOPICS = [
    {
        'name': 'Danish Renewable Energy Landscape',
        'description': 'Exploring wind energy and green transition in Denmark',
        'queries': [
            'vindmøller danmark',
            'grøn energi danske virksomheder',
            'havvind projekter Nordsøen',
            'energiø Bornholm',
            'Ørsted vindenergi strategi'
        ],
        'language': 'da',
        'issue_type': 'vindmøller'
    },
    {
        'name': 'AI Ethics and Governance Debate',
        'description': 'Mapping AI ethics concerns and regulatory frameworks',
        'queries': [
            'AI ethics concerns',
            'algorithmic bias examples',
            'AI regulation European Union',
            'artificial general intelligence risks',
            'AI safety alignment'
        ],
        'language': 'en',
        'issue_type': 'ai'
    },
    {
        'name': 'Climate Change Policy and Action',
        'description': 'Climate change discourse and mitigation strategies',
        'queries': [
            'climate emergency declaration',
            'Paris Agreement implementation',
            'net zero carbon targets',
            'climate adaptation strategies',
            'IPCC latest report findings'
        ],
        'language': 'en',
        'issue_type': 'climate'
    }
]


async def create_demo_user(session: AsyncSession) -> User:
    """
    Create or get demo user account.

    Args:
        session: Database session

    Returns:
        Demo User instance
    """
    # Check if demo user exists
    result = await session.execute(
        select(User).where(User.username == "demo_researcher")
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        print("Demo user already exists, using existing account")
        return existing_user

    # Create new demo user
    demo_user = User(
        username="demo_researcher",
        email="demo@issue-observatory.example",
        password_hash=get_password_hash("demo123"),
        is_admin=False,
        is_active=True
    )

    session.add(demo_user)
    await session.commit()
    await session.refresh(demo_user)

    print(f"Created demo user: {demo_user.username} (ID: {demo_user.id})")
    return demo_user


async def generate_search_session(
    session: AsyncSession,
    user: User,
    topic: dict,
    results_per_query: int = 30
) -> SearchSession:
    """
    Generate complete search session with synthetic data.

    Args:
        session: Database session
        user: User instance
        topic: Topic configuration dict
        results_per_query: Number of results per query

    Returns:
        SearchSession instance with all data
    """
    print(f"\n{'='*60}")
    print(f"Generating: {topic['name']}")
    print(f"{'='*60}")

    # Create search session
    search_session = SearchSession(
        user_id=user.id,
        name=topic['name'],
        description=topic['description'],
        status='completed',
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        config={'language': topic['language'], 'issue_type': topic['issue_type']}
    )

    session.add(search_session)
    await session.flush()  # Get session ID

    print(f"Created search session: {search_session.name} (ID: {search_session.id})")

    # Generate search results for each query
    query_count = 0
    result_count = 0
    content_count = 0
    noun_count = 0
    entity_count = 0

    for query_text in topic['queries']:
        query_count += 1
        print(f"\n  Query {query_count}/{len(topic['queries'])}: '{query_text}'")

        # Create query record
        search_query = SearchQuery(
            session_id=search_session.id,
            query_text=query_text,
            query_type='manual',
            status='completed'
        )
        session.add(search_query)
        await session.flush()

        # Generate synthetic search results
        synthetic_results = SearchResultFactory.create_search_results(
            query=query_text,
            num_results=results_per_query,
            language=topic['language'],
            seed=42 + query_count
        )

        print(f"    - Generated {len(synthetic_results)} search results")

        # Store search results
        for result_data in synthetic_results:
            search_result = SearchResult(
                query_id=search_query.id,
                url=result_data['url'],
                title=result_data['title'],
                description=result_data['description'],
                rank=result_data['rank'],
                source='synthetic',
                retrieved_at=result_data['retrieved_at']
            )
            session.add(search_result)
            result_count += 1

        # Generate website content for top 5 results
        top_results = synthetic_results[:5]
        for result_data in top_results:
            # Generate synthetic content
            content_data = WebsiteContentFactory.create_website_content(
                url=result_data['url'],
                issue_type=topic['issue_type'],
                depth=1,
                seed=42 + content_count
            )

            # Store website content
            website_content = WebsiteContent(
                user_id=user.id,
                url=content_data['url'],
                title=content_data['metadata']['title'],
                html_content=content_data['html'],
                text_content=content_data['text'],
                language=content_data['metadata']['language'],
                word_count=content_data['metadata']['word_count'],
                scraped_at=datetime.utcnow(),
                status='completed'
            )
            session.add(website_content)
            await session.flush()
            content_count += 1

            # Generate NLP extractions
            nlp_data = {
                'nouns': NLPDataFactory.generate_extracted_nouns(
                    content_data['text'],
                    language=topic['language'],
                    top_n=20,
                    seed=42 + content_count
                ),
                'entities': NLPDataFactory.generate_extracted_entities(
                    content_data['text'],
                    num_entities=10,
                    seed=42 + content_count
                )
            }

            # Store extracted nouns
            for noun_data in nlp_data['nouns']:
                extracted_noun = ExtractedNoun(
                    website_id=website_content.id,
                    text=noun_data['text'],
                    lemma=noun_data['lemma'],
                    count=noun_data['count'],
                    tfidf_score=noun_data['tfidf_score']
                )
                session.add(extracted_noun)
                noun_count += 1

            # Store extracted entities
            for entity_data in nlp_data['entities']:
                extracted_entity = ExtractedEntity(
                    website_id=website_content.id,
                    text=entity_data['text'],
                    entity_type=entity_data['type'],
                    count=entity_data['count'],
                    confidence=entity_data['confidence']
                )
                session.add(extracted_entity)
                entity_count += 1

        print(f"    - Created {len(top_results)} website contents with NLP data")

    # Generate networks
    print(f"\n  Generating networks...")

    # 1. Issue-website network
    issue_website_network = NetworkDataFactory.create_issue_website_network(
        num_queries=len(topic['queries']),
        num_websites=result_count,
        seed=42
    )

    gexf_data = NetworkDataFactory.export_to_gexf(issue_website_network)

    network_export_1 = NetworkExport(
        user_id=user.id,
        session_id=search_session.id,
        network_type='issue_website',
        name=f"{topic['name']} - Issue-Website Network",
        gexf_data=gexf_data,
        node_count=issue_website_network.number_of_nodes(),
        edge_count=issue_website_network.number_of_edges(),
        created_at=datetime.utcnow()
    )
    session.add(network_export_1)

    print(f"    - Issue-Website network: {issue_website_network.number_of_nodes()} nodes, "
          f"{issue_website_network.number_of_edges()} edges")

    # 2. Website-noun network
    website_noun_network = NetworkDataFactory.create_website_noun_network(
        num_websites=content_count,
        num_nouns=noun_count,
        seed=42
    )

    gexf_data = NetworkDataFactory.export_to_gexf(website_noun_network)

    network_export_2 = NetworkExport(
        user_id=user.id,
        session_id=search_session.id,
        network_type='website_noun',
        name=f"{topic['name']} - Website-Noun Network",
        gexf_data=gexf_data,
        node_count=website_noun_network.number_of_nodes(),
        edge_count=website_noun_network.number_of_edges(),
        created_at=datetime.utcnow()
    )
    session.add(network_export_2)

    print(f"    - Website-Noun network: {website_noun_network.number_of_nodes()} nodes, "
          f"{website_noun_network.number_of_edges()} edges")

    # 3. Website-concept knowledge graph
    concept_network = NetworkDataFactory.create_website_concept_network(
        num_websites=content_count,
        num_concepts=15,
        seed=42
    )

    gexf_data = NetworkDataFactory.export_to_gexf(concept_network)

    network_export_3 = NetworkExport(
        user_id=user.id,
        session_id=search_session.id,
        network_type='website_concept',
        name=f"{topic['name']} - Concept Knowledge Graph",
        gexf_data=gexf_data,
        node_count=concept_network.number_of_nodes(),
        edge_count=concept_network.number_of_edges(),
        created_at=datetime.utcnow()
    )
    session.add(network_export_3)

    print(f"    - Concept network: {concept_network.number_of_nodes()} nodes, "
          f"{concept_network.number_of_edges()} edges")

    # Commit all data
    await session.commit()

    print(f"\nCompleted '{topic['name']}':")
    print(f"  - {query_count} queries")
    print(f"  - {result_count} search results")
    print(f"  - {content_count} website contents")
    print(f"  - {noun_count} extracted nouns")
    print(f"  - {entity_count} extracted entities")
    print(f"  - 3 networks")

    return search_session


async def generate_all_demo_data(
    num_topics: int = 3,
    results_per_query: int = 30
):
    """
    Generate complete demo dataset.

    Args:
        num_topics: Number of topics to generate (max 3)
        results_per_query: Results per query
    """
    print("="*60)
    print("Issue Observatory Search - Demo Data Generation")
    print("="*60)

    # Create async engine
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        echo=False
    )

    # Create session maker
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        try:
            # Create demo user
            print("\nStep 1: Creating demo user...")
            demo_user = await create_demo_user(session)

            # Generate research topics
            print(f"\nStep 2: Generating {num_topics} research topics...")
            topics_to_generate = DEMO_TOPICS[:num_topics]

            sessions = []
            for i, topic in enumerate(topics_to_generate, 1):
                search_session = await generate_search_session(
                    session,
                    demo_user,
                    topic,
                    results_per_query
                )
                sessions.append(search_session)

            # Summary
            print("\n" + "="*60)
            print("DEMO DATA GENERATION COMPLETE")
            print("="*60)
            print(f"\nDemo User:")
            print(f"  Username: {demo_user.username}")
            print(f"  Email: {demo_user.email}")
            print(f"  Password: demo123")
            print(f"\nGenerated {len(sessions)} research topics:")
            for sess in sessions:
                print(f"  - {sess.name}")

            total_queries = sum(len(topic['queries']) for topic in topics_to_generate)
            total_results = total_queries * results_per_query
            total_content = total_queries * 5  # Top 5 per query
            total_networks = len(sessions) * 3  # 3 network types per session

            print(f"\nTotal synthetic data:")
            print(f"  - {len(sessions)} search sessions")
            print(f"  - {total_queries} search queries")
            print(f"  - {total_results} search results")
            print(f"  - {total_content} website contents")
            print(f"  - {total_content * 20} extracted nouns (approx)")
            print(f"  - {total_content * 10} extracted entities (approx)")
            print(f"  - {total_networks} networks")

            print("\nYou can now:")
            print("  1. Log in with demo user credentials")
            print("  2. Explore the generated research topics")
            print("  3. View networks and visualizations")
            print("  4. Test all application features with realistic data")

        except Exception as e:
            print(f"\nError generating demo data: {e}")
            raise

        finally:
            await engine.dispose()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate synthetic demo data for Issue Observatory Search'
    )
    parser.add_argument(
        '--num-topics',
        type=int,
        default=3,
        choices=[1, 2, 3],
        help='Number of research topics to generate (1-3)'
    )
    parser.add_argument(
        '--results-per-query',
        type=int,
        default=30,
        help='Number of search results per query'
    )

    args = parser.parse_args()

    # Run async generation
    asyncio.run(generate_all_demo_data(
        num_topics=args.num_topics,
        results_per_query=args.results_per_query
    ))


if __name__ == '__main__':
    main()
