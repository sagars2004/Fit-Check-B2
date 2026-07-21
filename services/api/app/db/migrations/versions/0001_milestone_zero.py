"""Create the Fit Check Milestone 0 metadata schema.

Revision ID: 0001_milestone_zero
Revises:
Create Date: 2026-07-21
"""

from alembic import op

from app.db.models import Base

revision = "0001_milestone_zero"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

