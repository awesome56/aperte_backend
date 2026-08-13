"""add source column to property and backfill from attributes

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b9
Create Date: 2026-08-13 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c3d4e5f6a7b9'
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_column('property', 'source'):
        op.add_column('property', sa.Column('source', sa.String(length=500), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE property SET source = (attributes::jsonb->>'source') "
        "WHERE attributes IS NOT NULL AND attributes::jsonb ? 'source';"
    ))
    conn.execute(sa.text(
        "UPDATE property SET attributes = ((attributes::jsonb) - 'source')::text "
        "WHERE attributes IS NOT NULL AND attributes::jsonb ? 'source';"
    ))


def downgrade():
    if sa.inspect(op.get_bind()).has_column('property', 'source'):
        op.drop_column('property', 'source')
