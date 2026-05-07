# =============================================================================
# PH Agent Hub — Admin API Router
# =============================================================================
# Tenant CRUD (admin-only) and User CRUD (admin + manager scoped).
# =============================================================================

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import (
    get_db,
    require_admin,
    require_admin_or_manager,
)
from ..core.exceptions import ForbiddenError
from ..db.orm.users import User as UserORM
from ..services.tenant_service import (
    create_tenant as _svc_create_tenant,
    delete_tenant as _svc_delete_tenant,
    list_tenants as _svc_list_tenants,
    update_tenant as _svc_update_tenant,
)
from ..services.user_service import (
    create_user as _svc_create_user,
    delete_user as _svc_delete_user,
    get_user_by_id,
    list_users as _svc_list_users,
    update_user as _svc_update_user,
)
from ..services.model_service import (
    create_model as _svc_create_model,
    delete_model as _svc_delete_model,
    get_model_by_id,
    list_models as _svc_list_models,
    update_model as _svc_update_model,
)
from ..services.tool_service import (
    create_tool as _svc_create_tool,
    delete_tool as _svc_delete_tool,
    get_tool_by_id,
    list_tools as _svc_list_tools,
    update_tool as _svc_update_tool,
)
from ..services.erpnext_service import (
    create_erpnext_instance as _svc_create_erpnext_instance,
    delete_erpnext_instance as _svc_delete_erpnext_instance,
    get_erpnext_instance_by_id,
    list_erpnext_instances as _svc_list_erpnext_instances,
    update_erpnext_instance as _svc_update_erpnext_instance,
)
from ..services.template_service import (
    create_template as _svc_create_template,
    delete_template as _svc_delete_template,
    get_template_by_id,
    list_template_tools as _svc_list_template_tools,
    list_templates as _svc_list_templates,
    update_template as _svc_update_template,
)
from ..services.skill_service import (
    create_skill as _svc_create_skill,
    delete_skill as _svc_delete_skill,
    get_skill_by_id,
    list_skill_tools as _svc_list_skill_tools,
    list_skills as _svc_list_skills,
    update_skill as _svc_update_skill,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# =============================================================================
# Pydantic Schemas
# =============================================================================


class TenantCreate(BaseModel):
    name: str


class TenantUpdate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    password: str
    display_name: str
    tenant_id: str
    role: str = "user"


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    tenant_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelCreate(BaseModel):
    name: str
    provider: str
    api_key: str
    base_url: str | None = None
    enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    routing_priority: int = 0


class ModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    enabled: bool | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    routing_priority: int | None = None


class ModelResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    provider: str
    base_url: str | None
    enabled: bool
    max_tokens: int
    temperature: float
    routing_priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolCreate(BaseModel):
    name: str
    type: str
    config: dict | None = None
    enabled: bool = True


class ToolUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class ToolResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    type: str
    config: dict | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ERPNextCreate(BaseModel):
    base_url: str
    api_key: str
    api_secret: str
    version: str


class ERPNextUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    version: str | None = None


class ERPNextResponse(BaseModel):
    id: str
    tenant_id: str
    base_url: str
    version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Tenant Endpoints (admin only)
# =============================================================================


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    _admin: UserORM = Depends(require_admin),
):
    """List all tenants (admin only)."""
    tenants = await _svc_list_tenants(db)
    return [TenantResponse.model_validate(t) for t in tenants]


@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _admin: UserORM = Depends(require_admin),
):
    """Create a new tenant (admin only)."""
    tenant = await _svc_create_tenant(db, body.name)
    return TenantResponse.model_validate(tenant)


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: UserORM = Depends(require_admin),
):
    """Update a tenant's name (admin only)."""
    tenant = await _svc_update_tenant(db, tenant_id, body.name)
    return TenantResponse.model_validate(tenant)


@router.delete("/tenants/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: UserORM = Depends(require_admin),
):
    """Delete a tenant (admin only)."""
    await _svc_delete_tenant(db, tenant_id)


# =============================================================================
# User Endpoints (admin or manager)
# =============================================================================


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """List users: admin sees all, manager sees own tenant only."""
    if current_user.role == "admin":
        users = await _svc_list_users(db)
    else:
        users = await _svc_list_users(db, tenant_id=current_user.tenant_id)
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Create a user. Admin: any tenant/role. Manager: own tenant, 'user' role only."""
    if current_user.role == "manager":
        if body.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only create users in their own tenant")
        if body.role != "user":
            raise ForbiddenError("Managers can only assign the 'user' role")

    user = await _svc_create_user(
        db,
        tenant_id=body.tenant_id,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        role=body.role,
    )
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Update a user. Managers scoped to own tenant with role restrictions."""
    target = await get_user_by_id(db, user_id)

    if current_user.role == "manager":
        # Manager can only modify users in their own tenant
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only modify users in their own tenant")
        # Manager cannot change tenant_id
        if body.tenant_id is not None and body.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers cannot change a user's tenant")
        # Manager cannot assign admin or manager roles
        if body.role is not None and body.role in ("admin", "manager"):
            raise ForbiddenError("Managers cannot assign admin or manager roles")
        # Manager cannot modify admins or managers
        if target.role in ("admin", "manager"):
            raise ForbiddenError("Managers cannot modify admin or manager users")

    # Build update kwargs from non-None fields
    update_kwargs: dict = {}
    if body.email is not None:
        update_kwargs["email"] = body.email
    if body.password is not None:
        update_kwargs["password"] = body.password
    if body.display_name is not None:
        update_kwargs["display_name"] = body.display_name
    if body.role is not None:
        update_kwargs["role"] = body.role
    if body.is_active is not None:
        update_kwargs["is_active"] = body.is_active
    if body.tenant_id is not None:
        update_kwargs["tenant_id"] = body.tenant_id

    user = await _svc_update_user(db, user_id, **update_kwargs)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Delete a user. Admin: any. Manager: own tenant, non-admin/manager only."""
    target = await get_user_by_id(db, user_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only delete users in their own tenant")
        if target.role in ("admin", "manager"):
            raise ForbiddenError("Managers cannot delete admin or manager users")

    await _svc_delete_user(db, user_id)


# =============================================================================
# Model Endpoints (admin or manager)
# =============================================================================


@router.get("/models", response_model=list[ModelResponse])
async def list_models(
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """List models. Admin sees all (optionally filtered by tenant),
    manager sees own tenant only."""
    if current_user.role == "manager":
        models = await _svc_list_models(db, tenant_id=current_user.tenant_id)
    else:
        models = await _svc_list_models(db, tenant_id=tenant_id)
    return [ModelResponse.model_validate(m) for m in models]


@router.post("/models", response_model=ModelResponse, status_code=201)
async def create_model(
    body: ModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Create a model. Manager always scoped to own tenant."""
    model = await _svc_create_model(
        db,
        tenant_id=current_user.tenant_id,
        name=body.name,
        provider=body.provider,
        api_key=body.api_key,
        base_url=body.base_url,
        enabled=body.enabled,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        routing_priority=body.routing_priority,
    )
    return ModelResponse.model_validate(model)


@router.put("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    body: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Update a model. Manager scoped to own tenant."""
    target = await get_model_by_id(db, model_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only modify models in their own tenant")

    update_kwargs: dict = {}
    if body.name is not None:
        update_kwargs["name"] = body.name
    if body.provider is not None:
        update_kwargs["provider"] = body.provider
    if body.api_key is not None:
        update_kwargs["api_key"] = body.api_key
    if body.base_url is not None:
        update_kwargs["base_url"] = body.base_url
    if body.enabled is not None:
        update_kwargs["enabled"] = body.enabled
    if body.max_tokens is not None:
        update_kwargs["max_tokens"] = body.max_tokens
    if body.temperature is not None:
        update_kwargs["temperature"] = body.temperature
    if body.routing_priority is not None:
        update_kwargs["routing_priority"] = body.routing_priority

    model = await _svc_update_model(db, model_id, **update_kwargs)
    return ModelResponse.model_validate(model)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Delete a model. Manager scoped to own tenant."""
    target = await get_model_by_id(db, model_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only delete models in their own tenant")

    await _svc_delete_model(db, model_id)


# =============================================================================
# Tool Endpoints (admin or manager)
# =============================================================================


@router.get("/tools", response_model=list[ToolResponse])
async def list_tools(
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """List tools. Admin sees all (optionally filtered by tenant),
    manager sees own tenant only."""
    if current_user.role == "manager":
        tools = await _svc_list_tools(db, tenant_id=current_user.tenant_id)
    else:
        tools = await _svc_list_tools(db, tenant_id=tenant_id)
    return [ToolResponse.model_validate(t) for t in tools]


@router.post("/tools", response_model=ToolResponse, status_code=201)
async def create_tool(
    body: ToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Create a tool. Manager always scoped to own tenant."""
    tool = await _svc_create_tool(
        db,
        tenant_id=current_user.tenant_id,
        name=body.name,
        type=body.type,
        config=body.config,
        enabled=body.enabled,
    )
    return ToolResponse.model_validate(tool)


@router.put("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    body: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Update a tool. Manager scoped to own tenant."""
    target = await get_tool_by_id(db, tool_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only modify tools in their own tenant")

    update_kwargs: dict = {}
    if body.name is not None:
        update_kwargs["name"] = body.name
    if body.type is not None:
        update_kwargs["type"] = body.type
    if body.config is not None:
        update_kwargs["config"] = body.config
    if body.enabled is not None:
        update_kwargs["enabled"] = body.enabled

    tool = await _svc_update_tool(db, tool_id, **update_kwargs)
    return ToolResponse.model_validate(tool)


@router.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Delete a tool. Manager scoped to own tenant."""
    target = await get_tool_by_id(db, tool_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only delete tools in their own tenant")

    await _svc_delete_tool(db, tool_id)


# =============================================================================
# ERPNext Instance Endpoints (admin or manager)
# =============================================================================


@router.get("/tools/erpnext", response_model=list[ERPNextResponse])
async def list_erpnext_instances(
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """List ERPNext instances. Admin sees all (optionally filtered by tenant),
    manager sees own tenant only."""
    if current_user.role == "manager":
        instances = await _svc_list_erpnext_instances(
            db, tenant_id=current_user.tenant_id
        )
    else:
        instances = await _svc_list_erpnext_instances(db, tenant_id=tenant_id)
    return [ERPNextResponse.model_validate(i) for i in instances]


@router.post("/tools/erpnext", response_model=ERPNextResponse, status_code=201)
async def create_erpnext_instance(
    body: ERPNextCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Create an ERPNext instance. Manager always scoped to own tenant."""
    instance = await _svc_create_erpnext_instance(
        db,
        tenant_id=current_user.tenant_id,
        base_url=body.base_url,
        api_key=body.api_key,
        api_secret=body.api_secret,
        version=body.version,
    )
    return ERPNextResponse.model_validate(instance)


@router.put("/tools/erpnext/{instance_id}", response_model=ERPNextResponse)
async def update_erpnext_instance(
    instance_id: str,
    body: ERPNextUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Update an ERPNext instance. Manager scoped to own tenant."""
    target = await get_erpnext_instance_by_id(db, instance_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError(
                "Managers can only modify ERPNext instances in their own tenant"
            )

    update_kwargs: dict = {}
    if body.base_url is not None:
        update_kwargs["base_url"] = body.base_url
    if body.api_key is not None:
        update_kwargs["api_key"] = body.api_key
    if body.api_secret is not None:
        update_kwargs["api_secret"] = body.api_secret
    if body.version is not None:
        update_kwargs["version"] = body.version

    instance = await _svc_update_erpnext_instance(db, instance_id, **update_kwargs)
    return ERPNextResponse.model_validate(instance)


@router.delete("/tools/erpnext/{instance_id}", status_code=204)
async def delete_erpnext_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Delete an ERPNext instance. Manager scoped to own tenant."""
    target = await get_erpnext_instance_by_id(db, instance_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError(
                "Managers can only delete ERPNext instances in their own tenant"
            )

    await _svc_delete_erpnext_instance(db, instance_id)


# =============================================================================
# Template Admin Endpoints (admin or manager)
# =============================================================================


class AdminTemplateCreate(BaseModel):
    title: str
    description: str
    system_prompt: str
    scope: str = "tenant"
    default_model_id: str | None = None
    assigned_user_id: str | None = None
    tool_ids: list[str] | None = None


class AdminTemplateUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    scope: str | None = None
    default_model_id: str | None = None
    assigned_user_id: str | None = None
    tool_ids: list[str] | None = None


class AdminTemplateResponse(BaseModel):
    id: str
    tenant_id: str
    title: str
    description: str
    system_prompt: str
    scope: str
    default_model_id: str | None
    assigned_user_id: str | None
    created_at: datetime
    updated_at: datetime
    tool_ids: list[str] = []

    model_config = {"from_attributes": True}


@router.get("/templates", response_model=list[AdminTemplateResponse])
async def admin_list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """List templates. Admin sees all. Manager sees own tenant only."""
    if current_user.role == "admin":
        # Admin sees all templates across all tenants
        from sqlalchemy import select
        from ..db.orm.templates import Template as TemplateORM
        result = await db.execute(select(TemplateORM).order_by(TemplateORM.created_at))
        templates = list(result.scalars().all())
    else:
        templates = await _svc_list_templates(
            db, tenant_id=current_user.tenant_id, current_user=current_user
        )

    resp_list: list[AdminTemplateResponse] = []
    for t in templates:
        tools = await _svc_list_template_tools(db, t.id)
        resp = AdminTemplateResponse.model_validate(t)
        resp.tool_ids = [tool.tool_id for tool in tools]
        resp_list.append(resp)

    return resp_list


@router.post("/templates", response_model=AdminTemplateResponse, status_code=201)
async def admin_create_template(
    body: AdminTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Create a template. Manager scoped to own tenant."""
    template = await _svc_create_template(
        db,
        tenant_id=current_user.tenant_id,
        title=body.title,
        description=body.description,
        system_prompt=body.system_prompt,
        scope=body.scope,
        default_model_id=body.default_model_id,
        assigned_user_id=body.assigned_user_id,
        tool_ids=body.tool_ids,
    )
    tools = await _svc_list_template_tools(db, template.id)
    resp = AdminTemplateResponse.model_validate(template)
    resp.tool_ids = [t.tool_id for t in tools]
    return resp


@router.put("/templates/{template_id}", response_model=AdminTemplateResponse)
async def admin_update_template(
    template_id: str,
    body: AdminTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Update a template. Manager scoped to own tenant."""
    target = await get_template_by_id(db, template_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only modify templates in their own tenant")

    update_kwargs: dict = {}
    if body.title is not None:
        update_kwargs["title"] = body.title
    if body.description is not None:
        update_kwargs["description"] = body.description
    if body.system_prompt is not None:
        update_kwargs["system_prompt"] = body.system_prompt
    if body.scope is not None:
        update_kwargs["scope"] = body.scope
    if body.default_model_id is not None:
        update_kwargs["default_model_id"] = body.default_model_id
    if body.assigned_user_id is not None:
        update_kwargs["assigned_user_id"] = body.assigned_user_id

    template = await _svc_update_template(
        db, template_id, tool_ids=body.tool_ids, **update_kwargs
    )
    tools = await _svc_list_template_tools(db, template.id)
    resp = AdminTemplateResponse.model_validate(template)
    resp.tool_ids = [t.tool_id for t in tools]
    return resp


@router.delete("/templates/{template_id}", status_code=204)
async def admin_delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Delete a template. Manager scoped to own tenant."""
    target = await get_template_by_id(db, template_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only delete templates in their own tenant")

    await _svc_delete_template(db, template_id)


# =============================================================================
# Skill Admin Endpoints (admin or manager)
# =============================================================================


class AdminSkillCreate(BaseModel):
    title: str
    description: str
    execution_type: str
    maf_target_key: str
    visibility: str = "tenant"
    template_id: str | None = None
    default_prompt_id: str | None = None
    default_model_id: str | None = None
    enabled: bool = True
    tool_ids: list[str] | None = None


class AdminSkillUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    execution_type: str | None = None
    maf_target_key: str | None = None
    visibility: str | None = None
    template_id: str | None = None
    default_prompt_id: str | None = None
    default_model_id: str | None = None
    enabled: bool | None = None
    tool_ids: list[str] | None = None


class AdminSkillResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str | None
    title: str
    description: str
    execution_type: str
    maf_target_key: str
    visibility: str
    template_id: str | None
    default_prompt_id: str | None
    default_model_id: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    tool_ids: list[str] = []

    model_config = {"from_attributes": True}


@router.get("/skills", response_model=list[AdminSkillResponse])
async def admin_list_skills(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """List skills. Admin sees all. Manager sees own tenant only."""
    if current_user.role == "admin":
        from sqlalchemy import select
        from ..db.orm.skills import Skill as SkillORM
        result = await db.execute(select(SkillORM).order_by(SkillORM.created_at))
        skills = list(result.scalars().all())
    else:
        skills = await _svc_list_skills(
            db, tenant_id=current_user.tenant_id
        )

    resp_list: list[AdminSkillResponse] = []
    for s in skills:
        tools = await _svc_list_skill_tools(db, s.id)
        resp = AdminSkillResponse.model_validate(s)
        resp.tool_ids = [t.tool_id for t in tools]
        resp_list.append(resp)

    return resp_list


@router.post("/skills", response_model=AdminSkillResponse, status_code=201)
async def admin_create_skill(
    body: AdminSkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Create a skill. Admin creates with specified visibility.
    Manager scoped to own tenant, creates tenant-shared skills."""
    skill = await _svc_create_skill(
        db,
        tenant_id=current_user.tenant_id,
        user_id=None,  # Admin-managed skills have no owner user
        title=body.title,
        description=body.description,
        execution_type=body.execution_type,
        maf_target_key=body.maf_target_key,
        visibility=body.visibility,
        template_id=body.template_id,
        default_prompt_id=body.default_prompt_id,
        default_model_id=body.default_model_id,
        enabled=body.enabled,
        tool_ids=body.tool_ids,
    )
    tools = await _svc_list_skill_tools(db, skill.id)
    resp = AdminSkillResponse.model_validate(skill)
    resp.tool_ids = [t.tool_id for t in tools]
    return resp


@router.put("/skills/{skill_id}", response_model=AdminSkillResponse)
async def admin_update_skill(
    skill_id: str,
    body: AdminSkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Update a skill. Manager scoped to own tenant."""
    target = await get_skill_by_id(db, skill_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only modify skills in their own tenant")

    update_kwargs: dict = {}
    for field in (
        "title", "description", "execution_type", "maf_target_key",
        "visibility", "template_id", "default_prompt_id", "default_model_id",
        "enabled",
    ):
        val = getattr(body, field, None)
        if val is not None:
            update_kwargs[field] = val

    skill = await _svc_update_skill(
        db, skill_id, tool_ids=body.tool_ids, **update_kwargs
    )
    tools = await _svc_list_skill_tools(db, skill.id)
    resp = AdminSkillResponse.model_validate(skill)
    resp.tool_ids = [t.tool_id for t in tools]
    return resp


@router.delete("/skills/{skill_id}", status_code=204)
async def admin_delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin_or_manager),
):
    """Delete a skill. Manager scoped to own tenant."""
    target = await get_skill_by_id(db, skill_id)

    if current_user.role == "manager":
        if target.tenant_id != current_user.tenant_id:
            raise ForbiddenError("Managers can only delete skills in their own tenant")

    await _svc_delete_skill(db, skill_id)
