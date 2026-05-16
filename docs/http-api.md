# HTTP 接口说明

## 1. 总体约定

- 新前端主契约是 `/api/*`
- 页面模板路由主要用于登录页、兼容入口和 `/admin`
- JSON API 未登录时返回 `401`
- 页面路由未登录时通常 `303` 跳转到 `/login`

## 2. 页面路由

### `GET /login`

- 返回登录页

### `POST /auth/login`

- 表单登录
- 成功后写入 session，跳转到 `/`

### `POST /auth/logout`

- 清空 session
- 跳转到 `/login`

### `GET /admin`

- 后端模板管理员页面
- 用于主机级配置与密码管理

### `POST /admin/settings`

- 提交管理员配置表单

### `POST /admin/password`

- 提交密码修改表单

## 3. 认证接口

### `GET /api/auth/session`

- 返回当前登录态

### `POST /api/auth/login`

- JSON 登录

### `POST /api/auth/logout`

- JSON 退出登录

## 4. 媒体接口

### `GET /api/videos`

- 视频列表
- 支持搜索与标签筛选

### `GET /api/videos/{video_id}`

- 单个视频详情

### `PATCH /api/videos/{video_id}/tags`

- 更新标签

### `POST /api/videos/{video_id}/like`

- 点赞或取消点赞

### `POST /api/videos/{video_id}/artwork`

- 更新封面或 poster

### `DELETE /api/videos/{video_id}`

- 创建删除任务

### `GET /api/videos/{video_id}/stream`

- 视频原始字节流
- 支持 Range

### `GET /api/videos/{video_id}/similar`

- 获取相似推荐

## 5. 导入与任务接口

### `POST /api/imports`

- 创建单文件导入任务

### `POST /api/imports/folders`

- 创建文件夹批量导入任务

### `GET /api/imports`

- 获取任务列表

### `GET /api/imports/{job_id}`

- 获取任务详情

### `POST /api/imports/{job_id}/cancel`

- 取消任务

### `POST /api/imports/{job_id}/retry`

- 重试失败任务

### `POST /api/imports/cancel-all`

- 取消全部活动任务

## 6. 缓存接口

### `GET /api/cache`

- 本地缓存摘要

### `GET /api/cache/videos`

- 已缓存视频列表

### `DELETE /api/cache`

- 清空全部缓存

### `DELETE /api/cache/videos/{video_id}`

- 清理单视频缓存

### `POST /api/videos/{video_id}/cache`

- 创建手动缓存任务

## 7. 设置接口

### `GET /api/settings`

- 公开运行设置

### `POST /api/settings`

- 更新运行设置

字段包括：

- `storage_backend`
- `baidu_root_path`
- `segment_cache_root_path`
- `cache_limit_bytes`
- `upload_transfer_concurrency`
- `download_transfer_concurrency`

### `POST /api/settings/baidu/oauth`

- 提交百度 OAuth 授权码

## 8. 管理员设置接口

### `GET /api/admin/settings`

- 获取管理员设置快照

当前返回字段包括：

- `playback_download_transfer_concurrency`
- `baidu_app_key`
- `baidu_secret_key`
- `baidu_sign_key`
- `baidu_oauth_redirect_uri`
- `session_secret`

### `POST /api/admin/settings`

- 更新管理员设置

当前可更新字段包括：

- `playback_download_transfer_concurrency`
- `baidu_app_key`
- `baidu_secret_key`
- `baidu_sign_key`
- `baidu_oauth_redirect_uri`
- `session_secret`

说明：

- 百度 App Key / Secret Key 保存后，OAuth 授权链接与百度存储访问会优先使用这些值
- `session_secret` 保存后需要重启后端才能完全生效

### `POST /api/admin/settings/password`

- 更新登录密码

## 9. Artwork 路由说明

- 新的前端统一使用 `/api/artwork/*`
- 后端兼容部分历史 `/covers/*` 路径
- 历史 `.jpg` poster 在需要时可回退到同名 `.avif`
