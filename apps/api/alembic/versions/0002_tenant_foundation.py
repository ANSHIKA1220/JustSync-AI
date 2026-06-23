"""tenant foundation

Revision ID: 0002_tenant_foundation
Revises: 0001_initial
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa
from app.database import Base
from app import models  # noqa: F401

revision = "0002_tenant_foundation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _first_org_id(connection):
    result = connection.execute(sa.text("SELECT id FROM organizations LIMIT 1")).first()
    return result[0] if result else None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("organizations"):
        Base.metadata.create_all(bind=connection)
        return

    org_id = _first_org_id(connection)

    op.add_column("organizations", sa.Column("slug", sa.String(length=80), nullable=True))
    op.add_column("organizations", sa.Column("plan", sa.String(length=40), nullable=True))
    op.add_column("organizations", sa.Column("status", sa.String(length=40), nullable=True))
    connection.execute(sa.text("UPDATE organizations SET slug = id WHERE slug IS NULL"))
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    connection.execute(sa.text("UPDATE organizations SET plan = 'trial' WHERE plan IS NULL"))
    connection.execute(sa.text("UPDATE organizations SET status = 'active' WHERE status IS NULL"))

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_organization_id"), "workspaces", ["organization_id"], unique=False)

    if org_id:
        connection.execute(
            sa.text(
                "INSERT INTO workspaces (id, organization_id, name, slug, is_default, created_at, updated_at) "
                "VALUES (:id, :organization_id, 'Customer Operations', 'customer-operations', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": "default-workspace", "organization_id": org_id},
        )

    for table_name in ("conversations", "support_tickets", "knowledge_documents", "routing_rules"):
        op.add_column(table_name, sa.Column("organization_id", sa.String(), nullable=True))
        if org_id:
            connection.execute(sa.text(f"UPDATE {table_name} SET organization_id = :org_id WHERE organization_id IS NULL"), {"org_id": org_id})
        op.create_index(op.f(f"ix_{table_name}_organization_id"), table_name, ["organization_id"], unique=False)

    op.add_column("audit_logs", sa.Column("organization_id", sa.String(), nullable=True))
    if org_id:
        connection.execute(sa.text("UPDATE audit_logs SET organization_id = :org_id WHERE organization_id IS NULL"), {"org_id": org_id})
    op.create_index(op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_audit_logs_organization_id"), table_name="audit_logs")
    op.drop_column("audit_logs", "organization_id")

    for table_name in ("routing_rules", "knowledge_documents", "support_tickets", "conversations"):
        op.drop_index(op.f(f"ix_{table_name}_organization_id"), table_name=table_name)
        op.drop_column(table_name, "organization_id")

    op.drop_index(op.f("ix_workspaces_organization_id"), table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_column("organizations", "status")
    op.drop_column("organizations", "plan")
    op.drop_column("organizations", "slug")
