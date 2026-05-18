"""add_maps_models

Revision ID: 94aa86728b56
Revises: ca4bed8ed6be
Create Date: 2026-05-18 22:42:47.606054

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '94aa86728b56'
down_revision = 'ca4bed8ed6be'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('port_location',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('country', sa.String(length=100), nullable=False),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_table('fishing_zone',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('zone_code', sa.String(length=30), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('geojson', sa.Text(), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False),
        sa.Column('zone_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone_code')
    )
    op.create_table('inspection_location',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inspection_id', sa.Integer(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspection.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inspection_id')
    )


def downgrade():
    op.drop_table('inspection_location')
    op.drop_table('fishing_zone')
    op.drop_table('port_location')
