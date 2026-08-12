"""add delivered to message for read receipts

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-08-12 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('message', sa.Column('delivered', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('message', 'delivered')
