"""add document_url to property_claim

Revision ID: f7a8b9c0d1e2
Revises: e6d7f8a9b0c1
Create Date: 2026-08-12 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'e6d7f8a9b0c1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('property_claim', sa.Column('document_url', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('property_claim', 'document_url')
