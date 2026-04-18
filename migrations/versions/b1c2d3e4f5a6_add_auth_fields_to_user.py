"""add auth fields to user (reset token, failed logins, locked_until)

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('reset_token',        sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('reset_token_expiry', sa.DateTime(),  nullable=True))
        batch_op.add_column(sa.Column('failed_logins',      sa.Integer(),   server_default='0'))
        batch_op.add_column(sa.Column('locked_until',       sa.DateTime(),  nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('reset_token')
        batch_op.drop_column('reset_token_expiry')
        batch_op.drop_column('failed_logins')
        batch_op.drop_column('locked_until')
