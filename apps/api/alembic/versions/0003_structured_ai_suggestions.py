"""structured ai suggestions

Revision ID: 0003_structured_ai_suggestions
Revises: 0002_tenant_foundation
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_structured_ai_suggestions"
down_revision = "0002_tenant_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_suggestions", sa.Column("repeat_contact", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ai_suggestions", sa.Column("repeat_contact_reason", sa.Text(), nullable=False, server_default=""))
    op.add_column("ai_suggestions", sa.Column("customer_history_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("ai_suggestions", sa.Column("conversation_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("ai_suggestions", sa.Column("routing_reason", sa.Text(), nullable=False, server_default=""))
    op.add_column("ai_suggestions", sa.Column("fallback_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ai_suggestions", sa.Column("fallback_reason", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("ai_suggestions", "fallback_reason")
    op.drop_column("ai_suggestions", "fallback_active")
    op.drop_column("ai_suggestions", "routing_reason")
    op.drop_column("ai_suggestions", "conversation_summary")
    op.drop_column("ai_suggestions", "customer_history_summary")
    op.drop_column("ai_suggestions", "repeat_contact_reason")
    op.drop_column("ai_suggestions", "repeat_contact")
