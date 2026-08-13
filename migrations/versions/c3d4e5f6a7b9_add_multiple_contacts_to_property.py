"""add multiple contact phones and emails to property

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-08-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b9'
down_revision = 'b2c3d4e5f6a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('property', sa.Column('contact_phones', sa.Text(), nullable=True))
    op.add_column('property', sa.Column('contact_emails', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('property', 'contact_emails')
    op.drop_column('property', 'contact_phones')
