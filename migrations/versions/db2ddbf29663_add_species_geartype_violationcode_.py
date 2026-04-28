"""add_species_geartype_violationcode_fields

Revision ID: db2ddbf29663
Revises: 1330580e428d
Create Date: 2026-04-28 22:29:31.738985

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db2ddbf29663'
down_revision = '1330580e428d'
branch_labels = None
depends_on = None


def upgrade():
    # ── New tables ────────────────────────────────────────────────────────
    op.create_table(
        'gear_type',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mesh_size_required', sa.Boolean(), nullable=False),
        sa.Column('min_mesh_size_mm', sa.Float(), nullable=True),
        sa.Column('is_legal', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_gear_type_code'),
    )
    op.create_table(
        'species',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name_bg', sa.String(length=150), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=True),
        sa.Column('scientific_name', sa.String(length=200), nullable=True),
        sa.Column('min_size_cm', sa.Float(), nullable=True),
        sa.Column('max_size_cm', sa.Float(), nullable=True),
        sa.Column('season_start', sa.String(length=10), nullable=True),
        sa.Column('season_end', sa.String(length=10), nullable=True),
        sa.Column('daily_limit_kg', sa.Float(), nullable=True),
        sa.Column('is_protected', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name_bg', name='uq_species_name_bg'),
    )

    # ── New columns on violation_codes ────────────────────────────────────
    with op.batch_alter_table('violation_codes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('law_article', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('default_penalty', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade():
    with op.batch_alter_table('violation_codes', schema=None) as batch_op:
        batch_op.drop_column('default_penalty')
        batch_op.drop_column('law_article')

    op.drop_table('species')
    op.drop_table('gear_type')
