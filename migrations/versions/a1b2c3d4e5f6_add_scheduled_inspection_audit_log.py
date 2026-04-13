"""add scheduled_inspection and audit_log tables

Revision ID: a1b2c3d4e5f6
Revises: 59be3e6d1be3
Create Date: 2026-04-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '59be3e6d1be3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduled_inspection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vessel_id', sa.Integer(), sa.ForeignKey('vessel.id'), nullable=False),
        sa.Column('inspector_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('scheduled_time', sa.String(10)),
        sa.Column('location', sa.String(255)),
        sa.Column('notes', sa.Text()),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('inspection_id', sa.Integer(), sa.ForeignKey('inspection.id'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('target_type', sa.String(50)),
        sa.Column('target_id', sa.Integer()),
        sa.Column('detail', sa.Text()),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('scheduled_inspection')
    op.drop_table('audit_log')
