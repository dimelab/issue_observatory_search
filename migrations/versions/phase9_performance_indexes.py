"""Phase 9: Add performance indexes for optimized queries.

Revision ID: phase9_performance_indexes
Revises: phase7_advanced_search_features
Create Date: 2025-10-25 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision: str = 'phase9_performance_indexes'
down_revision: Union[str, None] = 'phase7_advanced_search_features'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance indexes for optimized queries.

    Indexes added:
    1. Compound indexes for common query patterns
    2. Full-text search indexes
    3. Covering indexes for analysis queries
    4. Partial indexes for recent data
    """

    # ========================================================================
    # Search Sessions - Compound Indexes
    # ========================================================================

    # User sessions ordered by creation (most common query)
    op.create_index(
        'idx_search_sessions_user_created',
        'search_sessions',
        ['user_id', sa.text('created_at DESC')],
        postgresql_using='btree',
    )

    # User sessions by status (for filtering active/completed sessions)
    op.create_index(
        'idx_search_sessions_user_status',
        'search_sessions',
        ['user_id', 'status'],
        postgresql_using='btree',
    )

    # ========================================================================
    # Search Queries - Compound Indexes
    # ========================================================================

    # Session queries ordered by creation
    op.create_index(
        'idx_search_queries_session_created',
        'search_queries',
        ['session_id', sa.text('created_at DESC')],
        postgresql_using='btree',
    )

    # Queries by status for monitoring
    op.create_index(
        'idx_search_queries_status_created',
        'search_queries',
        ['status', sa.text('created_at DESC')],
        postgresql_using='btree',
    )

    # ========================================================================
    # Search Results - Compound Indexes
    # ========================================================================

    # Results by query ordered by rank (most common access pattern)
    op.create_index(
        'idx_search_results_query_rank',
        'search_results',
        ['query_id', 'rank'],
        postgresql_using='btree',
    )

    # Results by domain (for domain-based filtering)
    op.create_index(
        'idx_search_results_domain_created',
        'search_results',
        ['domain', sa.text('created_at DESC')],
        postgresql_using='btree',
    )

    # Unscraped results (for finding URLs to scrape)
    op.create_index(
        'idx_search_results_scraped_created',
        'search_results',
        ['scraped', sa.text('created_at DESC')],
        postgresql_where=sa.text('scraped = false'),
        postgresql_using='btree',
    )

    # ========================================================================
    # Website Content - Full-Text Search & Compound Indexes
    # ========================================================================

    # Full-text search on text content (for fast content search)
    op.execute("""
        CREATE INDEX idx_website_content_text_fts
        ON website_content
        USING gin(to_tsvector('english', COALESCE(text_content, '')))
    """)

    # Full-text search on title
    op.execute("""
        CREATE INDEX idx_website_content_title_fts
        ON website_content
        USING gin(to_tsvector('english', COALESCE(title, '')))
    """)

    # Content by domain and scraped time (for domain analysis)
    op.create_index(
        'idx_website_content_domain_scraped',
        'website_content',
        ['domain', sa.text('scraped_at DESC')],
        postgresql_using='btree',
    )

    # Analyzed content (for finding content to analyze)
    op.create_index(
        'idx_website_content_analyzed',
        'website_content',
        ['analyzed', sa.text('scraped_at DESC')],
        postgresql_using='btree',
    )

    # ========================================================================
    # Extracted Nouns - Covering Indexes for Analysis
    # ========================================================================

    # Nouns by content ordered by TF-IDF (for top nouns query)
    op.create_index(
        'idx_extracted_nouns_content_tfidf',
        'extracted_nouns',
        ['content_id', sa.text('tfidf_score DESC')],
        postgresql_using='btree',
    )

    # Nouns by session for session-level analysis
    op.create_index(
        'idx_extracted_nouns_session_tfidf',
        'extracted_nouns',
        ['session_id', sa.text('tfidf_score DESC')],
        postgresql_using='btree',
    )

    # High-scoring nouns (partial index for top terms)
    op.execute("""
        CREATE INDEX idx_extracted_nouns_high_tfidf
        ON extracted_nouns (session_id, tfidf_score DESC)
        WHERE tfidf_score > 0.1
    """)

    # ========================================================================
    # Entities - Compound Indexes
    # ========================================================================

    # Entities by content and type
    op.create_index(
        'idx_entities_content_type',
        'entities',
        ['content_id', 'entity_type'],
        postgresql_using='btree',
    )

    # Entities by session for session-level entity analysis
    op.create_index(
        'idx_entities_session_type',
        'entities',
        ['session_id', 'entity_type'],
        postgresql_using='btree',
    )

    # Full-text search on entity text
    op.execute("""
        CREATE INDEX idx_entities_text_fts
        ON entities
        USING gin(to_tsvector('english', entity_text))
    """)

    # ========================================================================
    # Network Exports - Compound Indexes
    # ========================================================================

    # Recent networks by user (partial index for 30 days)
    op.execute("""
        CREATE INDEX idx_network_exports_user_recent
        ON network_exports (user_id, created_at DESC)
        WHERE created_at > NOW() - INTERVAL '30 days'
    """)

    # Networks by session
    op.create_index(
        'idx_network_exports_session_created',
        'network_exports',
        ['session_id', sa.text('created_at DESC')],
        postgresql_using='btree',
    )

    # Networks by type
    op.create_index(
        'idx_network_exports_type_created',
        'network_exports',
        ['network_type', sa.text('created_at DESC')],
        postgresql_using='btree',
    )

    # ========================================================================
    # Scraping Jobs - Compound Indexes
    # ========================================================================

    # Jobs by session and status
    op.create_index(
        'idx_scraping_jobs_session_status',
        'scraping_jobs',
        ['session_id', 'status'],
        postgresql_using='btree',
    )

    # Pending/running jobs (partial index for active monitoring)
    op.execute("""
        CREATE INDEX idx_scraping_jobs_active
        ON scraping_jobs (created_at DESC)
        WHERE status IN ('pending', 'running')
    """)

    print("✅ Phase 9: Performance indexes created successfully")


def downgrade() -> None:
    """Remove performance indexes."""

    # Network exports
    op.drop_index('idx_network_exports_type_created', table_name='network_exports')
    op.drop_index('idx_network_exports_session_created', table_name='network_exports')
    op.execute('DROP INDEX IF EXISTS idx_network_exports_user_recent')

    # Entities
    op.execute('DROP INDEX IF EXISTS idx_entities_text_fts')
    op.drop_index('idx_entities_session_type', table_name='entities')
    op.drop_index('idx_entities_content_type', table_name='entities')

    # Extracted nouns
    op.execute('DROP INDEX IF EXISTS idx_extracted_nouns_high_tfidf')
    op.drop_index('idx_extracted_nouns_session_tfidf', table_name='extracted_nouns')
    op.drop_index('idx_extracted_nouns_content_tfidf', table_name='extracted_nouns')

    # Website content
    op.drop_index('idx_website_content_analyzed', table_name='website_content')
    op.drop_index('idx_website_content_domain_scraped', table_name='website_content')
    op.execute('DROP INDEX IF EXISTS idx_website_content_title_fts')
    op.execute('DROP INDEX IF EXISTS idx_website_content_text_fts')

    # Search results
    op.execute('DROP INDEX IF EXISTS idx_search_results_scraped_created')
    op.drop_index('idx_search_results_domain_created', table_name='search_results')
    op.drop_index('idx_search_results_query_rank', table_name='search_results')

    # Search queries
    op.drop_index('idx_search_queries_status_created', table_name='search_queries')
    op.drop_index('idx_search_queries_session_created', table_name='search_queries')

    # Search sessions
    op.drop_index('idx_search_sessions_user_status', table_name='search_sessions')
    op.drop_index('idx_search_sessions_user_created', table_name='search_sessions')

    # Scraping jobs
    op.execute('DROP INDEX IF EXISTS idx_scraping_jobs_active')
    op.drop_index('idx_scraping_jobs_session_status', table_name='scraping_jobs')

    print("✅ Phase 9: Performance indexes removed")
