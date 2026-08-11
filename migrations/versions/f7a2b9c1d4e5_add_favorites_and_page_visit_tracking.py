"""add favorite table, page_visit tracking table and property views column

Revision ID: f7a2b9c1d4e5
Revises: 76b2c49d5b58
Create Date: 2026-08-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a2b9c1d4e5'
down_revision = '76b2c49d5b58'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('favorite',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('property_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'property_id', name='uq_favorite_user_property')
    )

    op.create_table('page_visit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('visitor_id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('referrer', sa.String(length=255), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_page_visit_visitor_id'), 'page_visit', ['visitor_id'], unique=False)
    op.create_index(op.f('ix_page_visit_created_at'), 'page_visit', ['created_at'], unique=False)

    op.add_column('property', sa.Column('views', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('property', 'views')
    op.drop_index(op.f('ix_page_visit_created_at'), table_name='page_visit')
    op.drop_index(op.f('ix_page_visit_visitor_id'), table_name='page_visit')
    op.drop_table('page_visit')
    op.drop_table('favorite')
