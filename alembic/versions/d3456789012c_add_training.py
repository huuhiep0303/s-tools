"""Add training

Revision ID: d3456789012c
Revises: d2345678901b
Create Date: 2026-06-17 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3456789012c'
down_revision: Union[str, None] = 'd2345678901b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update RoleEnum to include MENTOR if not already present.
    # Postgres ENUM doesn't easily allow ALTER TYPE, but we are primarily using Enum(..., create_type=False) 
    # which relies on string values. If the DB enforces constraints, we might need manual SQL.
    # But Alembic default enum often just maps to VARCHAR in sqlite/postgres unless native enum is used.
    
    op.create_table('courses',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('mentor_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['mentor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_mentor_id'), 'courses', ['mentor_id'], unique=False)
    
    op.create_table('course_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('course_id', sa.String(length=36), nullable=False),
    sa.Column('session_number', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('materials_url', sa.String(), nullable=True),
    sa.Column('homework_desc', sa.Text(), nullable=True),
    sa.Column('homework_deadline', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_sessions_course_id'), 'course_sessions', ['course_id'], unique=False)

    op.create_table('course_members',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('course_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_members_course_id'), 'course_members', ['course_id'], unique=False)
    op.create_index(op.f('ix_course_members_user_id'), 'course_members', ['user_id'], unique=False)

def downgrade() -> None:
    op.drop_table('course_members')
    op.drop_table('course_sessions')
    op.drop_table('courses')
