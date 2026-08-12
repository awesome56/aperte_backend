"""add call and call_signal tables for in-app calling

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-08-12 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('call',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('caller_id', sa.Integer(), nullable=False),
    sa.Column('callee_id', sa.Integer(), nullable=False),
    sa.Column('call_type', sa.String(length=10), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('ended_by', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['callee_id'], ['user.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['caller_id'], ['user.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ended_by'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_status'), 'call', ['status'], unique=False)
    op.create_index(op.f('ix_call_created_at'), 'call', ['created_at'], unique=False)

    op.create_table('call_signal',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('call_id', sa.String(length=36), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('signal_type', sa.String(length=20), nullable=False),
    sa.Column('payload', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['call_id'], ['call.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_signal_call_id'), 'call_signal', ['call_id'], unique=False)
    op.create_index(op.f('ix_call_signal_created_at'), 'call_signal', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_call_signal_created_at'), table_name='call_signal')
    op.drop_index(op.f('ix_call_signal_call_id'), table_name='call_signal')
    op.drop_table('call_signal')
    op.drop_index(op.f('ix_call_created_at'), table_name='call')
    op.drop_index(op.f('ix_call_status'), table_name='call')
    op.drop_table('call')
