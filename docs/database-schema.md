# 数据库设计

## 1. 说明

项目当前使用 SQLite 作为本地主数据源。

它承担这些职责：

- 视频与标签元数据
- 导入 / 删除 / 缓存任务状态
- 分片元数据
- 运行设置与管理员设置
- 百度 refresh token / access token 等本地凭据状态
- 播放统计与推荐基础数据

数据库初始化仍采用启动时 bootstrap，而不是独立 migration 框架。

## 2. 关键表

### `videos`

保存视频主记录，包括：

- 标题
- 时长
- MIME 类型
- 大小
- 源文件路径
- 远端 manifest 路径
- artwork 路径
- 自定义 poster 标记

### `video_segments`

保存每个分片的：

- 分片序号
- 原始偏移与长度
- 密文大小
- 校验摘要
- nonce / tag
- 远端路径
- 本地缓存相对路径

当前 `local_staging_path` 使用缓存根目录相对后缀，而不是绝对路径。

### `import_jobs`

保存导入、删除、缓存等后台任务状态，包括：

- 任务类型
- 状态
- 进度
- 错误信息
- 关联视频

### `settings`

键值表，保存运行与管理员配置，例如：

- `storage_backend`
- `baidu_root_path`
- `segment_cache_root_path`
- `cache_limit_bytes`
- `upload_transfer_concurrency`
- `download_transfer_concurrency`
- `playback_download_transfer_concurrency`
- `password_hash`
- `baidu_app_key`
- `baidu_secret_key`
- `baidu_sign_key`
- `baidu_oauth_redirect_uri`
- `session_secret`
- `baidu_refresh_token`
- `baidu_access_token`

## 3. 设计取向

- 后端配置优先落库，减少首次使用必须手改环境变量的门槛
- 密码不存明文，只存 `password_hash`
- 远端访问凭据不回传到前端公开设置接口
- 分片缓存路径尽量相对化，便于目录迁移

## 4. 当前注意点

- `session_secret` 已允许持久化到数据库，但中间件仍在启动时初始化，所以完全生效需要重启
- 百度 App Key / Secret Key 现在允许保存在本地数据库；这是主机可信前提下的工程折中
- 历史数据兼容逻辑仍保留，用于旧路径、旧并发字段与旧 artwork 路径恢复
