"""add message table

Revision ID: a1b2c3d4e5f6
Revises: e5c1d2f3a4b6
Create Date: 2026-08-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e5c1d2f3a4b6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # The message table may already exist (it was created outside migrations).
    if 'message' not in inspector.get_table_names():
        op.create_table('message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receiver_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('read', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['property_id'], ['property.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['receiver_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['request_id'], ['request.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_message_sender_id'), 'message', ['sender_id'], unique=False)
        op.create_index(op.f('ix_message_receiver_id'), 'message', ['receiver_id'], unique=False)
        op.create_index(op.f('ix_message_created_at'), 'message', ['created_at'], unique=False)


def downgrade():
    if sa.inspect(op.get_bind()).has_table('message'):
        op.drop_index(op.f('ix_message_created_at'), table_name='message')
        op.drop_index(op.f('ix_message_receiver_id'), table_name='message')
        op.drop_index(op.f('ix_message_sender_id'), table_name='message')
        op.drop_table('message')
