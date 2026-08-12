"""add disabled flag to property

Revision ID: a1b2c3d4e5f7
Revises: f7a8b9c0d1e2
Create Date: 2026-08-13 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('property', sa.Column('disabled', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('property', 'disabled')
