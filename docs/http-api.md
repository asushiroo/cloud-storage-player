# HTTP 接口说明

## 认证约定

当前存在两类路由：

1. 页面路由
2. JSON API 路由

页面路由中的未登录访问通常会重定向到 `/login`。
JSON API 中的未登录访问会返回：

```json
{"detail":"Authentication required."}
```

HTTP 状态码为 `401`。

对于新的 Vue 前端，主认证契约是 `/api/auth/*`，而不是页面表单路由。

## 页面接口

### `GET /login`

用途：

- 返回登录页面

行为：

- 如果已经登录，会 `303` 跳转到 `/`

### `GET /`

用途：

- 返回当前占位首页

行为：

- 未登录时 `303` 跳转到 `/login`

### `POST /auth/login`

表单参数：

- `password`

行为：

- 密码正确：写入 Session，`303` 跳转到 `/`
- 密码错误：返回登录页，状态码 `401`

### `POST /auth/logout`

行为：

- 清空 Session
- `303` 跳转到 `/login`

这些页面路由当前只作为迁移期兼容层保留。

## JSON 认证接口

### `GET /api/auth/session`

用途：

- 读取当前登录态

认证：

- 不要求已登录

返回示例：

```json
{"authenticated": true}
```

### `POST /api/auth/login`

用途：

- Vue 前端提交密码登录

请求体：

```json
{"password": "shared-secret"}
```

成功：

- 返回 `200`
- 写入 Session Cookie
- 返回：

```json
{"authenticated": true}
```

失败：

- 返回 `401`

### `POST /api/auth/logout`

用途：

- Vue 前端退出登录

成功：

- 返回 `200`
- 清除 Session
- 返回：

```json
{"authenticated": false}
```

## 目录接口

### `GET /api/folders`

用途：

- 返回目录列表

认证：

- 需要登录

返回示例：

```json
[
  {
    "id": 1,
    "name": "Movies",
    "cover_path": "covers/movies.jpg",
    "created_at": "2026-05-09 21:00:00"
  }
]
```

排序：

- 按 `name`、`id` 升序

### `GET /api/videos`

用途：

- 返回视频列表

认证：

- 需要登录

查询参数：

- `folder_id`（可选）

返回字段：

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

### `GET /api/videos/{video_id}`

用途：

- 返回单个视频详情

认证：

- 需要登录

错误：

- 不存在时返回 `404`

## 设置接口

### `GET /api/settings`

用途：

- 读取当前公开的本地设置

认证：

- 需要登录

当前返回字段：

- `baidu_root_path`
- `cache_limit_bytes`

### `POST /api/settings`

用途：

- 更新当前公开的本地设置

认证：

- 需要登录

当前可更新字段：

- `baidu_root_path`
- `cache_limit_bytes`

说明：

- 当前接口不暴露 Baidu app key、secret key、sign key 这类敏感值
- 这些敏感值仍按仓库约定来自环境变量

## 导入接口

### `POST /api/imports`

用途：

- 通过主机本地文件路径创建一个导入任务

认证：

- 需要登录

请求体：

```json
{
  "source_path": "/tmp/demo.mp4",
  "folder_id": 1,
  "title": "Imported Demo"
}
```

字段说明：

- `source_path`
  - 必填
  - 必须是服务器本机上的真实文件路径
- `folder_id`
  - 可选
  - 如果提供，必须对应现有目录
- `title`
  - 可选
  - 不提供时默认使用文件名去掉扩展名后的 stem

当前行为：

1. 校验路径是否存在
2. 校验目录是否存在
3. 创建 `import_jobs` 记录
4. 调用 `ffprobe` 探测媒体信息
5. 写入 `videos` 记录
6. 尝试抽取封面
7. 更新任务状态为 `completed` 或 `failed`

成功返回：

- 状态码 `201`
- 返回导入任务详情

注意：

- 当前导入仍是**同步实现**
- 还没有上传百度网盘
- 还没有做切片、加密、manifest 生成
- 封面抽取失败不会阻塞视频元数据导入

### `GET /api/imports`

用途：

- 返回导入任务列表

认证：

- 需要登录

排序：

- 按 `id DESC`

### `GET /api/imports/{job_id}`

用途：

- 返回单个导入任务详情

认证：

- 需要登录

错误：

- 不存在时返回 `404`
