"""add voice note columns to message

Revision ID: f0a1b2c3d4e5
Revises: e7f8a9b0c1d2
Create Date: 2026-08-12 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0a1b2c3d4e5'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('message', sa.Column('voice_url', sa.String(length=500), nullable=True))
    op.add_column('message', sa.Column('voice_duration', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('message', 'voice_duration')
    op.drop_column('message', 'voice_url')
