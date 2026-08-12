"""add property_claim table

Revision ID: f5e6d7c8b9a0
Revises: f0a1b2c3d4e5
Create Date: 2026-08-12 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5e6d7c8b9a0'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('property_claim',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('property_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_property_claim_status'), 'property_claim', ['status'], unique=False)
    op.create_index(op.f('ix_property_claim_property_id'), 'property_claim', ['property_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_property_claim_property_id'), table_name='property_claim')
    op.drop_index(op.f('ix_property_claim_status'), table_name='property_claim')
    op.drop_table('property_claim')
