# HTTP 接口说明

## 认证约定

当前存在两类路由：

1. 页面兼容路由
2. JSON API 路由

对于新的 Vue 前端，主契约是 `/api/*`。

页面路由中的未登录访问通常会跳转到 `/login`；JSON API 未登录时返回：

```json
{"detail":"Authentication required."}
```

状态码为 `401`。

## 页面兼容接口

### `GET /login`

- 返回登录页
- 已登录时 `303` 跳转到 `/`

### `GET /`

- 返回当前兼容首页
- 未登录时 `303` 跳转到 `/login`

### `POST /auth/login`

- 表单参数：`password`
- 成功：写入 Session，`303` 跳转到 `/`
- 失败：返回 `401`

### `POST /auth/logout`

- 清空 Session
- `303` 跳转到 `/login`

这些接口当前只用于迁移兼容和简单 smoke 测试。

## JSON 认证接口

### `GET /api/auth/session`

用途：读取当前登录态。

返回示例：

```json
{"authenticated": true}
```

### `POST /api/auth/login`

请求体：

```json
{"password": "shared-secret"}
```

成功：

- `200`
- 写入 Session Cookie
- 返回：

```json
{"authenticated": true}
```

失败：

- `401`

### `POST /api/auth/logout`

成功：

- `200`
- 清除 Session
- 返回：

```json
{"authenticated": false}
```

## 目录接口

### `GET /api/folders`

- 需要登录
- 返回目录列表
- 按 `name`、`id` 升序

### `GET /api/videos`

- 需要登录
- 返回视频列表
- 可用查询参数：`folder_id`

返回字段包括：

- `id`
- `folder_id`
- `title`
- `cover_path`
- `mime_type`
- `size`
- `duration_seconds`
- `manifest_path`
- `source_path`
- `created_at`
- `segment_count`

### `GET /api/videos/{video_id}`

- 需要登录
- 返回单个视频详情
- 不存在时返回 `404`

## 播放接口

### `GET /api/videos/{video_id}/stream`

用途：返回浏览器播放器可直接消费的原始字节流。

认证：

- 需要登录

当前实现能力：

- 支持 `Accept-Ranges: bytes`
- 支持 `206 Partial Content`
- 支持单段 `Range`
- 支持 suffix range，例如 `bytes=-1024`

当前读取优先级：

1. 本地加密分片 staging
2. 当前配置的 storage backend
3. 本地源文件

注意：

- 浏览器拿到的仍是**原始视频字节**，不是加密分片
- 分片解密发生在服务端
- 当前 storage backend 可以是 `mock` 或 `baidu`

常见响应：

- `200`：未带 `Range`，返回整文件流
- `206`：有效范围请求
- `404`：视频不存在或本地/远端/源文件都不可用
- `416`：范围不可满足

## 导入接口

### `POST /api/imports`

用途：从 Windows 主机本地路径创建导入任务。

请求体示例：

```json
{
  "source_path": "D:/videos/demo.mp4",
  "folder_id": 1,
  "title": "Imported Demo"
}
```

当前处理行为：

1. 创建并推进 `import_jobs`
2. 探测媒体元数据
3. 创建 `videos`
4. 切片并加密
5. 写入 `video_segments`
6. 生成本地 manifest
7. 上传 manifest / 分片到当前 storage backend
8. 尝试抽取封面

成功时：

- 状态码 `201`
- 返回任务详情
- 当前同步实现下，通常已经是 `completed` 或 `failed`

### `GET /api/imports`

- 需要登录
- 返回导入任务列表

### `GET /api/imports/{job_id}`

- 需要登录
- 返回导入任务详情

## 设置接口

### `GET /api/settings`

- 需要登录
- 返回当前公开设置

当前字段：

- `baidu_root_path`
- `cache_limit_bytes`
- `storage_backend`
- `baidu_authorize_url`
- `baidu_has_refresh_token`

### `POST /api/settings`

- 需要登录
- 更新公开设置

当前可更新字段：

- `baidu_root_path`
- `cache_limit_bytes`
- `storage_backend`

说明：

- 当 `storage_backend=baidu` 时，`baidu_root_path` 必须以 `/apps/` 开头
- 当前默认值是 `/apps/CloudStoragePlayer`

### `POST /api/settings/baidu/oauth`

- 需要登录
- 提交百度授权页返回的 `code`
- 后端会换取并保存 refresh token

请求体示例：

```json
{"code":"your-baidu-auth-code"}
```

成功后：

- 返回最新设置快照
- `baidu_has_refresh_token` 会变成 `true`

说明：

- 当前接口不会返回 refresh token 明文
- `BAIDU_APP_KEY` 和 `BAIDU_SECRET_KEY` 仍必须由后端环境变量提供
