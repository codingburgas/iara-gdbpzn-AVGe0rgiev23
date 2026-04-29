"""add_fishing_trip_catch_record

Revision ID: cd90f020cade
Revises: db2ddbf29663
Create Date: 2026-04-29 22:56:11.161886

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cd90f020cade'
down_revision = 'db2ddbf29663'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'fishing_trip',
        sa.Column('id',             sa.Integer(),        nullable=False),
        sa.Column('fisherman_id',   sa.Integer(),        nullable=False),
        sa.Column('vessel_id',      sa.Integer(),        nullable=True),
        sa.Column('start_datetime', sa.DateTime(),       nullable=False),
        sa.Column('end_datetime',   sa.DateTime(),       nullable=True),
        sa.Column('location',       sa.String(255),      nullable=True),
        sa.Column('weather',        sa.String(100),      nullable=True),
        sa.Column('fuel_liters',    sa.Float(),          nullable=True),
        sa.Column('notes',          sa.Text(),           nullable=True),
        sa.Column('status',         sa.String(20),       nullable=False),
        sa.Column('created_at',     sa.DateTime(),       nullable=True),
        sa.ForeignKeyConstraint(['fisherman_id'], ['users.id']),
        sa.ForeignKeyConstraint(['vessel_id'],    ['vessel.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'catch_record',
        sa.Column('id',                sa.Integer(),    nullable=False),
        sa.Column('trip_id',           sa.Integer(),    nullable=False),
        sa.Column('species_id',        sa.Integer(),    nullable=True),
        sa.Column('species_name_free', sa.String(150),  nullable=True),
        sa.Column('quantity',          sa.Integer(),    nullable=False),
        sa.Column('weight_kg',         sa.Float(),      nullable=False),
        sa.Column('size_cm',           sa.Float(),      nullable=True),
        sa.Column('gear_type_id',      sa.Integer(),    nullable=True),
        sa.Column('notes',             sa.Text(),       nullable=True),
        sa.Column('created_at',        sa.DateTime(),   nullable=True),
        sa.ForeignKeyConstraint(['gear_type_id'], ['gear_type.id']),
        sa.ForeignKeyConstraint(['species_id'],   ['species.id']),
        sa.ForeignKeyConstraint(['trip_id'],      ['fishing_trip.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('catch_record')
    op.drop_table('fishing_trip')
