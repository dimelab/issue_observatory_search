"""v6.0.0 keyword and NER enhancements

Revision ID: v6_0_0_enhancements
Revises: phase9_performance_indexes
Create Date: 2025-12-09 12:00:00.000000

This migration adds v6.0.0 enhancements:
- New fields to extracted_nouns for multiple extraction methods
- New fields to extracted_entities for transformer NER
- Indexes for performance
- Backward compatibility maintained
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v6_0_0_enhancements'
down_revision = 'phase9_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add v6.0.0 enhancements to analysis tables.

    Changes:
    1. extracted_nouns (keywords):
       - Add extraction_method column (noun, all_pos, tfidf, rake)
       - Add phrase_length column (for n-grams)
       - Add pos_tag column (for POS filtering)

    2. extracted_entities:
       - Make confidence NOT NULL with default 1.0
       - Add frequency column
       - Add extraction_method column (spacy, transformer)
    """

    # ===== Update extracted_nouns table =====

    # Add new columns for v6.0.0 keyword extraction
    op.add_column(
        'extracted_nouns',
        sa.Column(
            'extraction_method',
            sa.String(length=50),
            nullable=False,
            server_default='noun',
            comment='Extraction method: noun, all_pos, tfidf, rake'
        )
    )

    op.add_column(
        'extracted_nouns',
        sa.Column(
            'phrase_length',
            sa.Integer(),
            nullable=True,
            comment='Number of words in keyword phrase (for n-grams)'
        )
    )

    op.add_column(
        'extracted_nouns',
        sa.Column(
            'pos_tag',
            sa.String(length=20),
            nullable=True,
            comment='Part of speech tag: NOUN, VERB, ADJ, etc.'
        )
    )

    # Create indexes for new columns
    op.create_index(
        'ix_extracted_nouns_extraction_method',
        'extracted_nouns',
        ['extraction_method']
    )

    op.create_index(
        'ix_extracted_nouns_pos_tag',
        'extracted_nouns',
        ['pos_tag']
    )

    # Create composite index for filtering by method and score
    op.create_index(
        'ix_extracted_nouns_method_score',
        'extracted_nouns',
        ['extraction_method', 'tfidf_score'],
        postgresql_using='btree'
    )

    # ===== Update extracted_entities table =====

    # Make confidence NOT NULL with default (for existing rows)
    op.execute(
        """
        UPDATE extracted_entities
        SET confidence = 1.0
        WHERE confidence IS NULL
        """
    )

    op.alter_column(
        'extracted_entities',
        'confidence',
        existing_type=sa.Float(),
        nullable=False,
        server_default='1.0'
    )

    # Add frequency column
    op.add_column(
        'extracted_entities',
        sa.Column(
            'frequency',
            sa.Integer(),
            nullable=False,
            server_default='1',
            comment='Number of times this entity appears in the text'
        )
    )

    # Add extraction_method column
    op.add_column(
        'extracted_entities',
        sa.Column(
            'extraction_method',
            sa.String(length=50),
            nullable=False,
            server_default='spacy',
            comment='Extraction method: spacy or transformer'
        )
    )

    # Create indexes for new columns
    op.create_index(
        'ix_extracted_entities_confidence',
        'extracted_entities',
        ['confidence']
    )

    op.create_index(
        'ix_extracted_entities_extraction_method',
        'extracted_entities',
        ['extraction_method']
    )

    # Create composite index for filtering by method and confidence
    op.create_index(
        'ix_extracted_entities_method_confidence',
        'extracted_entities',
        ['extraction_method', 'confidence'],
        postgresql_using='btree'
    )

    # Create composite index for label and confidence (common query pattern)
    op.create_index(
        'ix_extracted_entities_label_confidence',
        'extracted_entities',
        ['label', 'confidence'],
        postgresql_using='btree'
    )


def downgrade() -> None:
    """
    Revert v6.0.0 enhancements.

    This removes the new columns and indexes added in the upgrade.
    """

    # ===== Revert extracted_entities changes =====

    # Drop indexes
    op.drop_index('ix_extracted_entities_label_confidence', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_method_confidence', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_extraction_method', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_confidence', table_name='extracted_entities')

    # Drop columns
    op.drop_column('extracted_entities', 'extraction_method')
    op.drop_column('extracted_entities', 'frequency')

    # Revert confidence to nullable
    op.alter_column(
        'extracted_entities',
        'confidence',
        existing_type=sa.Float(),
        nullable=True,
        server_default=None
    )

    # ===== Revert extracted_nouns changes =====

    # Drop indexes
    op.drop_index('ix_extracted_nouns_method_score', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_pos_tag', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_extraction_method', table_name='extracted_nouns')

    # Drop columns
    op.drop_column('extracted_nouns', 'pos_tag')
    op.drop_column('extracted_nouns', 'phrase_length')
    op.drop_column('extracted_nouns', 'extraction_method')
