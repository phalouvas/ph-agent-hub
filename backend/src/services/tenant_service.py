# =============================================================================
# PH Agent Hub — Tenant Service (CRUD)
# =============================================================================

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ConflictError, NotFoundError
from ..db.orm.tenants import Tenant


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    """Return all tenants."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    return list(result.scalars().all())


async def get_tenant_by_id(db: AsyncSession, tenant_id: str) -> Tenant | None:
    """Look up a tenant by primary key."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def create_tenant(db: AsyncSession, name: str) -> Tenant:
    """Create a new tenant. Raises ConflictError if the name already exists."""
    existing = await db.execute(select(Tenant).where(Tenant.name == name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A tenant with this name already exists")

    tenant = Tenant(name=name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def update_tenant(db: AsyncSession, tenant_id: str, name: str) -> Tenant:
    """Update a tenant's name. Raises NotFoundError or ConflictError."""
    tenant = await get_tenant_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")

    duplicate = await db.execute(
        select(Tenant).where(Tenant.name == name, Tenant.id != tenant_id)
    )
    if duplicate.scalar_one_or_none() is not None:
        raise ConflictError("A tenant with this name already exists")

    tenant.name = name
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def delete_tenant(db: AsyncSession, tenant_id: str) -> None:
    """Delete a tenant by ID. Raises NotFoundError if missing, ConflictError
    if the tenant still has active resources (users, models, sessions, etc.).
    Audit/usage logs are auto-cleaned up (they are historical records)."""
    tenant = await get_tenant_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")

    # ------------------------------------------------------------------
    # Auto-cleanup: historical records that shouldn't block deletion
    # ------------------------------------------------------------------
    from ..db.orm.audit_logs import AuditLog
    from ..db.orm.usage_logs import UsageLog

    await db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
    await db.execute(delete(UsageLog).where(UsageLog.tenant_id == tenant_id))
    await db.flush()

    # ------------------------------------------------------------------
    # Blocker check: active resources that must be handled manually
    # ------------------------------------------------------------------
    blockers: list[str] = []

    from ..db.orm.users import User
    from ..db.orm.sessions import Session as SessionORM
    from ..db.orm.tools import Tool
    from ..db.orm.templates import Template
    from ..db.orm.skills import Skill
    from ..db.orm.tags import Tag as TagORM
    from ..db.orm.memory import Memory
    from ..db.orm.file_uploads import FileUpload
    from ..db.orm.models import Model as ModelORM
    from ..db.orm.groups import UserGroup
    from ..db.orm.prompts import Prompt
    from ..db.orm.rag import RAGDocument

    checks: list[tuple[str, type]] = [
        ("users", User),
        ("models", ModelORM),
        ("sessions", SessionORM),
        ("tools", Tool),
        ("templates", Template),
        ("skills", Skill),
        ("tags", TagORM),
        ("memories", Memory),
        ("file uploads", FileUpload),
        ("user groups", UserGroup),
        ("prompts", Prompt),
        ("RAG documents", RAGDocument),
    ]

    for label, model in checks:
        result = await db.execute(
            select(func.count()).select_from(model).where(
                getattr(model, "tenant_id") == tenant_id
            )
        )
        count = result.scalar() or 0
        if count > 0:
            blockers.append(f"{count} {label}")

    if blockers:
        raise ConflictError(
            "Cannot delete this tenant — it still has related data: "
            + ", ".join(blockers)
            + ". Remove or reassign all related resources first."
        )

    await db.delete(tenant)
    await db.commit()


async def force_delete_tenant(db: AsyncSession, tenant_id: str) -> None:
    """Cascade-delete a tenant and ALL related data.

    Deletion order respects FK dependency chains (leaf tables first):
    1. message_feedback, session_tags, session_active_tools,
       skill_allowed_tools, template_allowed_tools,
       tool_groups, model_groups, user_group_members
    2. messages, memory, file_uploads (S3 first, then DB)
    3. prompts, skills, templates, sessions
    4. tags, rag_documents, tools, models, user_groups
    5. usage_logs, audit_logs, users
    6. tenant itself

    Also deletes S3 objects for all file_uploads belonging to the tenant
    before removing the DB rows.  Raises NotFoundError if the tenant does
    not exist.
    """
    from sqlalchemy import select as _select, delete as _delete

    from ..db.orm.tenants import Tenant
    from ..db.orm.users import User as UserORM
    from ..db.orm.models import Model as ModelORM
    from ..db.orm.sessions import Session as SessionORM, SessionActiveTool
    from ..db.orm.tools import Tool
    from ..db.orm.templates import Template, TemplateAllowedTool
    from ..db.orm.skills import Skill, SkillAllowedTool
    from ..db.orm.tags import Tag as TagORM, SessionTag
    from ..db.orm.memory import Memory
    from ..db.orm.file_uploads import FileUpload
    from ..db.orm.groups import UserGroup, UserGroupMember, ModelGroup, ToolGroup
    from ..db.orm.prompts import Prompt
    from ..db.orm.rag import RAGDocument
    from ..db.orm.messages import Message, MessageFeedback
    from ..db.orm.usage_logs import UsageLog
    from ..db.orm.audit_logs import AuditLog

    # Verify the tenant exists
    result = await db.execute(_select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Tenant not found")

    # ==================================================================
    # Step 0 — Delete S3 objects for all file uploads in this tenant
    # ==================================================================
    from ..storage.s3 import delete_object

    uploads_result = await db.execute(
        _select(FileUpload.storage_key, FileUpload.bucket).where(
            FileUpload.tenant_id == tenant_id
        )
    )
    uploads = uploads_result.all()
    for storage_key, bucket in uploads:
        try:
            await delete_object(bucket, storage_key)
        except Exception:
            # Best-effort S3 cleanup — don't block tenant deletion
            pass

    # ==================================================================
    # Step 1 — Leaf junction / association tables (no dependents of their own)
    # ==================================================================
    await db.execute(
        _delete(MessageFeedback).where(
            MessageFeedback.message_id.in_(
                _select(Message.id).where(
                    Message.session_id.in_(
                        _select(SessionORM.id).where(
                            SessionORM.tenant_id == tenant_id
                        )
                    )
                )
            )
        )
    )
    await db.execute(
        _delete(SessionTag).where(
            SessionTag.session_id.in_(
                _select(SessionORM.id).where(SessionORM.tenant_id == tenant_id)
            )
        )
    )
    await db.execute(
        _delete(SessionActiveTool).where(
            SessionActiveTool.session_id.in_(
                _select(SessionORM.id).where(SessionORM.tenant_id == tenant_id)
            )
        )
    )
    await db.execute(
        _delete(SkillAllowedTool).where(
            SkillAllowedTool.skill_id.in_(
                _select(Skill.id).where(Skill.tenant_id == tenant_id)
            )
        )
    )
    await db.execute(
        _delete(TemplateAllowedTool).where(
            TemplateAllowedTool.template_id.in_(
                _select(Template.id).where(Template.tenant_id == tenant_id)
            )
        )
    )
    await db.execute(
        _delete(ToolGroup).where(
            ToolGroup.group_id.in_(
                _select(UserGroup.id).where(UserGroup.tenant_id == tenant_id)
            )
        )
    )
    await db.execute(
        _delete(ModelGroup).where(
            ModelGroup.group_id.in_(
                _select(UserGroup.id).where(UserGroup.tenant_id == tenant_id)
            )
        )
    )
    await db.execute(
        _delete(UserGroupMember).where(
            UserGroupMember.group_id.in_(
                _select(UserGroup.id).where(UserGroup.tenant_id == tenant_id)
            )
        )
    )
    await db.flush()

    # ==================================================================
    # Step 2 — Tables with FKs to tables deleted in step 4/5
    # ==================================================================
    await db.execute(
        _delete(Memory).where(Memory.tenant_id == tenant_id)
    )
    await db.execute(
        _delete(FileUpload).where(FileUpload.tenant_id == tenant_id)
    )
    await db.execute(
        _delete(Message).where(
            Message.session_id.in_(
                _select(SessionORM.id).where(SessionORM.tenant_id == tenant_id)
            )
        )
    )
    await db.flush()

    # ==================================================================
    # Step 3 — Tables referencing users + parent tables
    # ==================================================================
    await db.execute(
        _delete(Prompt).where(Prompt.tenant_id == tenant_id)
    )
    # Skills FK to default_prompt_id (SET NULL), so prompts can be deleted first
    await db.execute(
        _delete(Skill).where(Skill.tenant_id == tenant_id)
    )
    # Sessions FK to skills (nullable), templates (nullable), models (nullable)
    await db.execute(
        _delete(SessionORM).where(SessionORM.tenant_id == tenant_id)
    )
    # Templates FK to models (nullable), users (nullable)
    await db.execute(
        _delete(Template).where(Template.tenant_id == tenant_id)
    )
    await db.flush()

    # ==================================================================
    # Step 4 — Tables referencing only tenants (no cross-table FKs)
    # ==================================================================
    await db.execute(_delete(TagORM).where(TagORM.tenant_id == tenant_id))
    await db.execute(_delete(RAGDocument).where(RAGDocument.tenant_id == tenant_id))
    await db.execute(_delete(Tool).where(Tool.tenant_id == tenant_id))
    await db.execute(_delete(ModelORM).where(ModelORM.tenant_id == tenant_id))
    await db.execute(_delete(UserGroup).where(UserGroup.tenant_id == tenant_id))
    await db.flush()

    # ==================================================================
    # Step 5 — Historical records (FK to users, models)
    # ==================================================================
    await db.execute(
        _delete(UsageLog).where(UsageLog.tenant_id == tenant_id)
    )
    await db.execute(
        _delete(AuditLog).where(AuditLog.tenant_id == tenant_id)
    )
    await db.flush()

    # ==================================================================
    # Step 6 — Users (FK to tenants)
    # ==================================================================
    await db.execute(
        _delete(UserORM).where(UserORM.tenant_id == tenant_id)
    )
    await db.flush()

    # ==================================================================
    # Step 7 — The tenant itself
    # ==================================================================
    await db.delete(tenant)
    await db.commit()
