"""add visitor_session and analytics_event tables

Revision ID: e5c1d2f3a4b6
Revises: f7a2b9c1d4e5
Create Date: 2026-08-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5c1d2f3a4b6'
down_revision = 'f7a2b9c1d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('visitor_session',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('visitor_id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('last_activity_at', sa.DateTime(), nullable=True),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('page_views', sa.Integer(), nullable=True),
    sa.Column('landing_path', sa.String(length=255), nullable=False),
    sa.Column('landing_title', sa.String(length=255), nullable=True),
    sa.Column('exit_path', sa.String(length=255), nullable=True),
    sa.Column('referrer', sa.String(length=255), nullable=True),
    sa.Column('source_type', sa.String(length=20), nullable=True),
    sa.Column('utm_source', sa.String(length=100), nullable=True),
    sa.Column('utm_medium', sa.String(length=100), nullable=True),
    sa.Column('utm_campaign', sa.String(length=100), nullable=True),
    sa.Column('utm_term', sa.String(length=100), nullable=True),
    sa.Column('utm_content', sa.String(length=100), nullable=True),
    sa.Column('device_type', sa.String(length=20), nullable=True),
    sa.Column('browser', sa.String(length=50), nullable=True),
    sa.Column('os', sa.String(length=50), nullable=True),
    sa.Column('screen_size', sa.String(length=30), nullable=True),
    sa.Column('country', sa.String(length=4), nullable=True),
    sa.Column('is_bounce', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_visitor_session_visitor_id'), 'visitor_session', ['visitor_id'], unique=False)
    op.create_index(op.f('ix_visitor_session_started_at'), 'visitor_session', ['started_at'], unique=False)
    op.create_index(op.f('ix_visitor_session_last_activity_at'), 'visitor_session', ['last_activity_at'], unique=False)

    op.create_table('analytics_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('visitor_id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('properties', sa.Text(), nullable=True),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('referrer', sa.String(length=255), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('time_on_page_ms', sa.Integer(), nullable=True),
    sa.Column('device_type', sa.String(length=20), nullable=True),
    sa.Column('browser', sa.String(length=50), nullable=True),
    sa.Column('os', sa.String(length=50), nullable=True),
    sa.Column('screen_size', sa.String(length=30), nullable=True),
    sa.Column('country', sa.String(length=4), nullable=True),
    sa.Column('source_type', sa.String(length=20), nullable=True),
    sa.Column('utm_source', sa.String(length=100), nullable=True),
    sa.Column('utm_medium', sa.String(length=100), nullable=True),
    sa.Column('utm_campaign', sa.String(length=100), nullable=True),
    sa.Column('utm_term', sa.String(length=100), nullable=True),
    sa.Column('utm_content', sa.String(length=100), nullable=True),
    sa.Column('ttfb', sa.Integer(), nullable=True),
    sa.Column('dom_loaded', sa.Integer(), nullable=True),
    sa.Column('load_time', sa.Integer(), nullable=True),
    sa.Column('fcp', sa.Integer(), nullable=True),
    sa.Column('lcp', sa.Integer(), nullable=True),
    sa.Column('cls', sa.Float(), nullable=True),
    sa.Column('js_errors', sa.Integer(), nullable=True),
    sa.Column('failed_requests', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analytics_event_session_id'), 'analytics_event', ['session_id'], unique=False)
    op.create_index(op.f('ix_analytics_event_visitor_id'), 'analytics_event', ['visitor_id'], unique=False)
    op.create_index(op.f('ix_analytics_event_event_type'), 'analytics_event', ['event_type'], unique=False)
    op.create_index(op.f('ix_analytics_event_path'), 'analytics_event', ['path'], unique=False)
    op.create_index(op.f('ix_analytics_event_property_id'), 'analytics_event', ['property_id'], unique=False)
    op.create_index(op.f('ix_analytics_event_created_at'), 'analytics_event', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_analytics_event_created_at'), table_name='analytics_event')
    op.drop_index(op.f('ix_analytics_event_property_id'), table_name='analytics_event')
    op.drop_index(op.f('ix_analytics_event_path'), table_name='analytics_event')
    op.drop_index(op.f('ix_analytics_event_event_type'), table_name='analytics_event')
    op.drop_index(op.f('ix_analytics_event_visitor_id'), table_name='analytics_event')
    op.drop_index(op.f('ix_analytics_event_session_id'), table_name='analytics_event')
    op.drop_table('analytics_event')
    op.drop_index(op.f('ix_visitor_session_last_activity_at'), table_name='visitor_session')
    op.drop_index(op.f('ix_visitor_session_started_at'), table_name='visitor_session')
    op.drop_index(op.f('ix_visitor_session_visitor_id'), table_name='visitor_session')
    op.drop_table('visitor_session')
