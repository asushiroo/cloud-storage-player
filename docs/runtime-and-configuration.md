# 运行与配置

## 1. 运行前提

- Python 3.12
- UV
- Node.js / npm
- `FFmpeg`
- `FFprobe`

## 2. 初始化与启动

后端：

```bash
uv sync --dev
uv run cloud-storage-player
```

前端开发：

```bash
npm install
npm run dev
```

默认地址：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`
- 管理员页：`http://127.0.0.1:8000/admin`

## 3. 启动时行为

后端启动后会：

1. 读取基础环境变量与 `.env`
2. 初始化数据库
3. 创建必要目录
4. 初始化导入 worker、manifest 同步调度器和播放缓存刷写注册表
5. 挂载 Session 中间件和 CORS
6. 注册 API 路由和页面路由
7. 在启用时挂载 `frontend/dist`

## 4. 配置来源

当前配置来源分成三层：

### 环境变量 / `.env`

适合启动前基础配置与兼容回退。

### `/admin`

适合主机管理员填写的首次配置项：

- 百度 App Key / Secret Key / Sign Key
- 百度 OAuth 回调地址
- 会话密钥
- 播放回退下载并发
- 登录密码

### `/settings`

适合日常运行配置：

- 存储后端
- 百度根路径
- 缓存目录
- 缓存上限
- 上传并发
- 下载并发

## 5. 环境变量

### `CSP_` 前缀变量

- `CSP_APP_NAME`
- `CSP_HOST`
- `CSP_PORT`
- `CSP_SESSION_SECRET`
- `CSP_PASSWORD`
- `CSP_PASSWORD_HASH`
- `CSP_DATABASE_PATH`
- `CSP_FFPROBE_BINARY`
- `CSP_FFMPEG_BINARY`
- `CSP_COVERS_PATH`
- `CSP_CONTENT_KEY_PATH`
- `CSP_SEGMENT_STAGING_PATH`
- `CSP_SEGMENT_SIZE_BYTES`
- `CSP_STORAGE_BACKEND`
- `CSP_REMOTE_TRANSFER_CONCURRENCY`
- `CSP_UPLOAD_TRANSFER_CONCURRENCY`
- `CSP_DOWNLOAD_TRANSFER_CONCURRENCY`
- `CSP_BAIDU_UPLOAD_RESUME_POLL_INTERVAL_SECONDS`
- `CSP_BAIDU_OAUTH_REDIRECT_URI`
- `CSP_MOCK_STORAGE_PATH`
- `CSP_CORS_ALLOWED_ORIGINS_RAW`

### 百度开放平台变量

这组变量不带 `CSP_` 前缀：

- `BAIDU_APP_KEY`
- `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY`

说明：

- 现在百度凭据优先读取 `/admin` 保存的数据库值
- 环境变量仍保留为兼容回退

## 6. 当前管理员配置策略

### 立即生效

- 百度 App Key / Secret Key
- 百度 OAuth 回调地址
- 播放回退下载并发
- 登录密码

### 重启后完全生效

- `session_secret`

原因：

- Session 中间件在应用启动时初始化，运行中不适合无缝替换签名密钥

## 7. 百度首次接入流程

建议流程：

1. 启动后端
2. 打开 `/admin`
3. 填写百度 App Key / Secret Key
4. 打开前端 `/settings`
5. 进入百度授权页
6. 拿到 `code`
7. 提交到 `/api/settings/baidu/oauth`

## 8. 本地重要路径

- 数据库：`data/cloud_storage_player.db`
- 封面：`data/covers`
- 内容密钥：`data/keys/content.key`
- 默认分片缓存目录：`data/segments`
- 默认 mock 远端目录：`data/mock-remote`

这些路径若为相对路径，按项目运行根目录解析。

## 9. 存储模式

### `mock`

- 用本地目录模拟远端对象存储
- 便于开发、测试和离线验证

### `baidu`

- 通过百度网盘官方 OpenAPI 访问远端对象
- 依赖本地 refresh token 和百度开放平台凭据

## 10. 常用验证

后端测试：

```bash
uv run pytest
```

前端构建：

```bash
npm run build
```

Windows 打包：

```bash
npm run build:csp
```
