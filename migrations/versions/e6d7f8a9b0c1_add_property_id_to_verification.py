"""add property_id to verification for claim verification codes

Revision ID: e6d7f8a9b0c1
Revises: f5e6d7c8b9a0
Create Date: 2026-08-12 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6d7f8a9b0c1'
down_revision = 'f5e6d7c8b9a0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('verification', sa.Column('property_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_verification_property', 'verification', 'property', ['property_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint('fk_verification_property', 'verification', type_='foreignkey')
    op.drop_column('verification', 'property_id')
