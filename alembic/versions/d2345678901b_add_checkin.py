"""Add checkin

Revision ID: d2345678901b
Revises: d1234567890a
Create Date: 2026-06-16 23:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2345678901b'
down_revision: Union[str, None] = 'd1234567890a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('checkin_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('secret_code', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_checkin_sessions_secret_code'), 'checkin_sessions', ['secret_code'], unique=True)
    
    op.create_table('checkin_records',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('scanned_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['checkin_sessions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('checkin_records')
    op.drop_index(op.f('ix_checkin_sessions_secret_code'), table_name='checkin_sessions')
    op.drop_table('checkin_sessions')
