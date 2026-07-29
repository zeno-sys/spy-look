# 控制台账号密码鉴权设计

> 本文档描述 Spy-Look 管理台的账号密码鉴权体系：首次部署强制初始化、Cookie Session、唯一 Owner + 多 Admin、本机重置 Owner 密码。与对外网关 `/v1` 的 API Key 鉴权相互独立。

---

## 1. 背景与目标

### 1.1 问题

在引入本能力之前：

- 管理台 UI 与所有管理 API（`*/admin/*`、`/gateway/logs` 等）完全开放
- 仅 `/v1` 网关使用 Bearer API Key
- 若服务暴露到内网/外网，任何人可改上游密钥、读日志、改配置

### 1.2 目标

| 目标 | 说明 |
| ---- | ---- |
| 控制台大门 | 未登录不能使用管理台与管理 API |
| 无自助注册 | 账号由 Owner 在后台创建 |
| 首次部署可引导 | 系统无用户时强制进入初始化页 |
| 与网关解耦 | `/v1` 仍只用现有 API Key，不要求控制台登录 |
| 可运维 | Owner 忘密时可在本机重置，无需邮件/短信 |

### 1.3 非目标

- 自助注册、OAuth、邮箱找回
- 多 Owner / 角色转让
- 强制 HTTPS
- IP 级限流（仅账号登录失败锁定）
- CLI 重置密码

---

## 2. 角色与能力

系统有且仅有 **1 个 Owner**，可有多个 **Admin**。

| 能力 | Owner | Admin |
| ---- | ----- | ----- |
| 使用全部工具与管理 API | ✅ | ✅ |
| 创建 Admin 账号 | ✅ | ❌ |
| 禁用 / 启用 / 删除 Admin | ✅ | ❌ |
| 重置他人密码 | ✅ | ❌ |
| 强制下线（作废会话） | ✅ | ❌ |
| 修改自己的密码 | ✅ | ✅ |
| 修改用户名 | ❌ | ❌ |
| 看到「用户管理」菜单 | ✅ | ❌ |

硬约束：

- 初始化页创建的第一个账号固定为 Owner，之后不可转让、不可再建第二个 Owner
- 不可删除 / 禁用 Owner；Owner 不可删除自己
- 创建用户时角色固定为 `admin`

---

## 3. 总体架构

```
┌─────────────┐     Cookie Session      ┌──────────────────────┐
│  管理台 UI   │ ──────────────────────► │  FastAPI 后端         │
│  Vue Router │                         │  /auth + 管理 API    │
└─────────────┘                         └──────────┬───────────┘
                                                   │
                                          ConsoleAuthMiddleware
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ▼                              ▼                              ▼
             /auth 公开接口                  需登录的管理 API                   /v1 网关
          (status/setup/login…)           (默认拒绝未登录)               Bearer API Key
```

### 3.1 鉴权边界

| 路径 | 鉴权 |
| ---- | ---- |
| `/v1/*` | 现有 Bearer API Key（与控制台无关） |
| `/healthz` | 公开 |
| `/assets/*`、SPA 前端路由 | 公开（前端路由守卫再拦） |
| `/auth/status`、`/auth/setup`、`/auth/login`、`/auth/local-reset-owner` | 公开（各自有业务约束） |
| 其余 `/auth/*` | 需登录；用户管理需 Owner |
| `/gateway/*`、`/video-tools/*`、`/doc-tools/*`、`/image-tools/*`、`/agent-resources/*`、`/settings/*` 等管理前缀 | 需有效 Session |

采用 **默认拒绝管理前缀**：不只匹配 `*/admin`，避免漏掉如 `/gateway/logs` 这类非 admin 命名的管理接口。

---

## 4. 核心流程

### 4.1 首次部署

```
访问任意管理台页面
        │
        ▼
  GET /auth/status
        │
   initialized?
    /         \
  否           是
  │            │
  ▼            ▼
/setup      已登录？
创建 Owner     /     \
设 Cookie  否       是
进首页     /login   进页面
```

- `POST /auth/setup` 仅在用户数为 0 时可用
- 创建角色固定为 `owner`，成功后直接下发 Session Cookie

### 4.2 日常登录

- `POST /auth/login`：校验用户名密码、账号禁用、锁定状态
- 支持 `remember`：
  - 未勾选：浏览器会话 Cookie + 服务端最长 12 小时
  - 勾选：Cookie `Max-Age` 30 天 + 服务端 30 天
- 绝对上限均为 30 天

### 4.3 登录失败锁定

- 同一账号连续失败 **5** 次 → 锁定 **15** 分钟
- 锁定期间即使密码正确也拒绝（HTTP 423）
- 成功登录后清零失败计数

### 4.4 会话作废

以下操作会立刻作废该用户**全部**会话（含当前）：

- 本人修改密码
- Owner 重置他人密码
- 本机重置 Owner 密码
- 禁用账号
- 删除账号
- Owner 主动「强制下线」

修改密码后前端引导重新登录。

### 4.5 本机重置 Owner 密码

适用场景：唯一 Owner 忘记密码，且无法通过其他已登录 Owner 重置（系统只有一个 Owner）。

1. 在**运行服务的机器上**用浏览器打开：`http://127.0.0.1:<port>/local-reset`
2. 调用 `POST /auth/local-reset-owner`
3. 校验条件（同时满足）：
   - 直连 peer 为 `127.0.0.1` / `::1` / `localhost`（**不信任** `X-Forwarded-For`）
   - 请求 `Host` 也为本机名（防止花生壳等反代把外网流量伪装成本机）
4. 重置唯一 Owner 密码并作废其全部会话

外网域名访问该接口一律 403。

---

## 5. 数据模型

表由 SQLModel 在启动时 `create_all` 创建（与项目其他表一致；schema 变更时需删库重建）。

### 5.1 `spy_look_users`

| 字段 | 说明 |
| ---- | ---- |
| `id` | 主键 |
| `username` | 唯一；1–64 位，字母/数字开头，可含 `. _ -` |
| `password_hash` | bcrypt |
| `role` | `owner` \| `admin` |
| `disabled` | 是否禁用 |
| `failed_login_count` | 连续失败次数 |
| `locked_until` | 锁定截止时间（UTC） |
| `created_at` / `updated_at` | 时间戳 |

### 5.2 `spy_look_sessions`

| 字段 | 说明 |
| ---- | ---- |
| `id` | Session Token（`secrets.token_urlsafe(32)`），作 Cookie 值 |
| `user_id` | 外键 → users |
| `expires_at` | 过期时间 |
| `remember` | 是否「记住我」 |
| `created_at` / `last_seen_at` | 创建与最近访问 |

允许多端同时登录（同一用户可有多条未过期 Session）。

---

## 6. API 一览

前缀：`/auth`

| 方法 | 路径 | 权限 | 说明 |
| ---- | ---- | ---- | ---- |
| GET | `/status` | 公开 | `{ initialized, user? }` |
| POST | `/setup` | 未初始化 | 创建 Owner 并登录 |
| POST | `/login` | 公开 | 登录；body: `username, password, remember` |
| POST | `/logout` | 登录 | 删除当前会话并清 Cookie |
| POST | `/change-password` | 登录 | 本人改密；作废全部会话 |
| POST | `/local-reset-owner` | 本机 | 重置 Owner 密码 |
| GET | `/users` | Owner | 用户列表 |
| POST | `/users` | Owner | 创建 Admin |
| POST | `/users/{id}/disabled` | Owner | 启用/禁用 |
| DELETE | `/users/{id}` | Owner | 删除 |
| POST | `/users/{id}/reset-password` | Owner | 重置密码 |
| POST | `/users/{id}/revoke-sessions` | Owner | 强制下线 |

密码规则：至少 **8** 位。

Cookie 名：`spy_look_session`

| 属性 | 值 |
| ---- | -- |
| HttpOnly | 是 |
| SameSite | Lax |
| Path | `/` |
| Secure | 仅当请求为 HTTPS 时为 true（允许纯 HTTP 自托管） |

---

## 7. 关键代码位置

| 区域 | 路径 |
| ---- | ---- |
| 模型 | `api/db/models.py`（`SpyLookUser` / `SpyLookSession`） |
| 用户与会话仓储 | `api/db/users.py` |
| Auth 路由与依赖 | `api/tools/auth/` |
| 全局中间件 | `api/tools/auth/middleware.py`（挂载于 `api/main.py`） |
| 前端 API | `ui/src/composables/useApi.ts`（`credentials: 'include'`） |
| 前端鉴权状态 | `ui/src/composables/useAuth.ts` |
| 路由守卫 | `ui/src/router/index.ts` |
| 页面 | `ui/src/views/auth/*`；设置页「账号安全」；侧栏用户信息 |

开发代理：`ui/vite.config.ts` 需代理 `/auth` → 后端。

---

## 8. 前端行为

### 8.1 公开页（无 AppLayout）

- `/setup` — 首次初始化
- `/login` — 登录（含「记住我」）
- `/local-reset` — 本机重置 Owner

### 8.2 路由守卫

1. 拉取 `/auth/status`
2. 未初始化 → 强制 `/setup`
3. 已初始化未登录 → `/login`（`/local-reset` 仍可进）
4. 已登录访问 login/setup → 回首页
5. `meta.ownerOnly`（如 `/settings/users`）非 Owner → 回首页

### 8.3 Owner 入口

- 侧栏：「用户管理」→ `/settings/users`
- 侧栏：当前用户名 / 角色、退出登录
- 设置 →「账号安全」：修改密码

Admin 不展示用户管理；即使直链也由 API 返回 403。

---

## 9. 安全说明

| 项 | 做法 |
| -- | ---- |
| 密码存储 | bcrypt |
| Session | 随机高熵 Token，仅存服务端表 + HttpOnly Cookie |
| CSRF | 同源 + SameSite=Lax；管理台与 API 同域部署 |
| 本机重置 | peer + Host 双重校验，不信任转发头 |
| 爆破 | 账号级失败锁定 |
| 网关 | `/v1` 独立 API Key，控制台登录不替代网关鉴权 |

部署建议：

- 生产尽量 HTTPS；HTTP 时 Cookie 无 Secure，适合内网/花生壳等自托管场景
- 勿将未鉴权的旧版本暴露到公网
- Owner 密码务必妥善保存；忘密走本机重置页

---

## 10. 运维备忘

| 场景 | 操作 |
| ---- | ---- |
| 全新部署 | 打开站点 → `/setup` 设置 Owner |
| Owner 忘密 | 本机访问 `http://127.0.0.1:<port>/local-reset` |
| 增加使用者 | Owner 登录 → 用户管理 → 新建 Admin |
| 踢人 / 离职 | 禁用或删除账号，或「强制下线」 |
| Schema 升级需重建用户表 | 按项目惯例删除 `api/spy_look.db` 后重启（会清空全部业务数据，慎用） |

---

## 11. 与网关 API Key 的关系

```
外部调用方 ──Bearer API Key──► /v1/*     （不经过控制台登录）
管理员浏览器 ──Cookie Session──► 管理台 API （不替代 /v1 鉴权）
```

两套凭证用途不同：

- **控制台账号**：保护「谁能改配置、看日志、管用户」
- **Client API Key**：保护「谁能调用对外 LLM 网关」

控制台登录**不能**用来调用 `/v1`；持有 API Key **也不能**进入管理台。
