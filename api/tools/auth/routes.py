from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.users import (
    ROLE_ADMIN,
    ROLE_OWNER,
    clear_login_failures,
    count_users,
    create_session,
    create_user,
    delete_session,
    delete_user,
    get_owner,
    get_user_by_id,
    get_user_by_username,
    is_user_locked,
    list_users,
    record_login_failure,
    revoke_user_sessions,
    set_user_disabled,
    update_user_password,
    user_public,
    validate_password,
    validate_username,
)
from tools.auth.deps import AuthContext, get_optional_auth, require_auth, require_owner
from tools.auth.password import hash_password, verify_password
from tools.auth.schemas import (
    ChangePasswordRequest,
    CreateUserRequest,
    LocalResetOwnerRequest,
    LoginRequest,
    ResetPasswordRequest,
    SetDisabledRequest,
    SetupRequest,
)
from tools.auth.session_cookie import (
    clear_session_cookie,
    is_loopback,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def auth_status(
    ctx: AuthContext | None = Depends(get_optional_auth),
    session: AsyncSession = Depends(get_session),
) -> dict:
    initialized = (await count_users(session)) > 0
    return {
        "initialized": initialized,
        "user": user_public(ctx.user) if ctx else None,
    }


@router.post("/setup")
async def auth_setup(
    body: SetupRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await count_users(session) > 0:
        raise HTTPException(status_code=400, detail="系统已初始化，无法重复设置")
    try:
        username = validate_username(body.username)
        password = validate_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = await create_user(
        session,
        username=username,
        password_hash=hash_password(password),
        role=ROLE_OWNER,
    )
    public = user_public(user)
    sess = await create_session(session, user_id=int(user.id), remember=False)
    set_session_cookie(response, request, sess)
    return {"ok": True, "user": public}


@router.post("/login")
async def auth_login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await count_users(session) == 0:
        raise HTTPException(status_code=400, detail="系统尚未初始化")

    username = str(body.username or "").strip()
    user = await get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.disabled:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    if is_user_locked(user):
        raise HTTPException(status_code=423, detail="登录失败次数过多，请稍后再试")

    if not verify_password(body.password, user.password_hash):
        await record_login_failure(session, user)
        if is_user_locked(user):
            raise HTTPException(status_code=423, detail="登录失败次数过多，请稍后再试")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    await clear_login_failures(session, user)
    public = user_public(user)
    sess = await create_session(session, user_id=int(user.id), remember=bool(body.remember))
    set_session_cookie(response, request, sess)
    return {"ok": True, "user": public}


@router.post("/logout")
async def auth_logout(
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await delete_session(session, ctx.session_id)
    clear_session_cookie(response, request)
    return {"ok": True}


@router.post("/change-password")
async def auth_change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    try:
        new_password = validate_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await update_user_password(session, ctx.user, hash_password(new_password))
    await revoke_user_sessions(session, ctx.user.id)
    clear_session_cookie(response, request)
    return {"ok": True, "relogin_required": True}


@router.post("/local-reset-owner")
async def auth_local_reset_owner(
    body: LocalResetOwnerRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not is_loopback(request):
        raise HTTPException(status_code=403, detail="仅允许本机访问")
    owner = await get_owner(session)
    if not owner:
        raise HTTPException(status_code=400, detail="尚未初始化 Owner 账号")
    try:
        new_password = validate_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await update_user_password(session, owner, hash_password(new_password))
    await revoke_user_sessions(session, owner.id)
    return {"ok": True}


@router.get("/users")
async def auth_list_users(
    _: AuthContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    users = await list_users(session)
    return {"items": [user_public(u) for u in users]}


@router.post("/users")
async def auth_create_user(
    body: CreateUserRequest,
    _: AuthContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        username = validate_username(body.username)
        password = validate_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = await get_user_by_username(session, username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = await create_user(
        session,
        username=username,
        password_hash=hash_password(password),
        role=ROLE_ADMIN,
    )
    return {"ok": True, "user": user_public(user)}


@router.post("/users/{user_id}/disabled")
async def auth_set_user_disabled(
    user_id: int,
    body: SetDisabledRequest,
    ctx: AuthContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == ROLE_OWNER:
        raise HTTPException(status_code=400, detail="不能禁用 Owner 账号")
    if user.id == ctx.user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")

    user_id_int = int(user.id)
    await set_user_disabled(session, user, bool(body.disabled))
    if body.disabled:
        await revoke_user_sessions(session, user_id_int)
    refreshed = await get_user_by_id(session, user_id_int)
    return {"ok": True, "user": user_public(refreshed or user)}


@router.delete("/users/{user_id}")
async def auth_delete_user(
    user_id: int,
    ctx: AuthContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == ROLE_OWNER:
        raise HTTPException(status_code=400, detail="不能删除 Owner 账号")
    if user.id == ctx.user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    await delete_user(session, user)
    return {"ok": True}


@router.post("/users/{user_id}/reset-password")
async def auth_reset_user_password(
    user_id: int,
    body: ResetPasswordRequest,
    ctx: AuthContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == ctx.user.id:
        raise HTTPException(status_code=400, detail="请使用「修改密码」修改自己的密码")
    try:
        new_password = validate_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await update_user_password(session, user, hash_password(new_password))
    await revoke_user_sessions(session, user.id)
    return {"ok": True}


@router.post("/users/{user_id}/revoke-sessions")
async def auth_revoke_user_sessions(
    user_id: int,
    _: AuthContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    count = await revoke_user_sessions(session, user.id)
    return {"ok": True, "revoked": count}
