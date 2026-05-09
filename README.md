# Cloud Storage Player

这是一个运行在 Windows 主机上的局域网视频服务，目标是将加密后的分片存储到百度网盘，并向浏览器回放原始视频字节流。

## 当前进度

仓库目前已经实现的最小切片包括：

- 使用 UV 管理 Python 项目与依赖
- FastAPI 应用入口
- 前后端分离架构骨架
- Vue 3 + TypeScript + Vite 前端目录
- 基于 Cookie Session 的单密码认证
- `/api/auth/*` JSON 认证接口
- SQLite 初始化与基础表结构
- `folders` / `videos` / `settings` 仓储层
- 受保护的只读目录接口
- 视频详情接口
- 本地文件导入任务与 `ffprobe` 媒体探测
- 导入时封面抽取与 `/covers/*` 静态访问
- 设置读写 API
- 认证、目录、导入、设置接口测试

当前**还没有实现**：

- 百度网盘接入
- 视频分片与加密
- 清单同步
- Range 播放流

## Python 版本

项目当前目标版本为 `Python 3.12`。

## 快速开始

```bash
uv sync --dev
uv run cloud-storage-player
```

默认监听：

- Host: `0.0.0.0`
- Port: `8000`

应用首次启动时会自动创建 SQLite 数据库文件。

## 环境变量

配置从 `.env` 文件或带 `CSP_` 前缀的环境变量中读取。

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
- `CSP_CORS_ALLOWED_ORIGINS_RAW`

说明：

- `CSP_SESSION_SECRET` 部署前必须修改。
- 如果设置了 `CSP_PASSWORD_HASH`，它会优先于 `CSP_PASSWORD`。
- 如果两者都未设置，默认密码为 `admin`。
- `CSP_DATABASE_PATH` 默认值为 `data/cloud_storage_player.db`。
- `CSP_COVERS_PATH` 默认值为 `data/covers`。
- `CSP_CORS_ALLOWED_ORIGINS_RAW` 默认允许 Vue dev server 来源。

## 当前已实现接口

认证接口：

- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`

兼容页面接口：

- `GET /login`
- `GET /`
- `POST /auth/login`
- `POST /auth/logout`

目录接口：

- `GET /api/folders`
- `GET /api/videos`
- `GET /api/videos/{video_id}`

导入接口：

- `POST /api/imports`
- `GET /api/imports`
- `GET /api/imports/{job_id}`

设置接口：

- `GET /api/settings`
- `POST /api/settings`

其中 `/api/*` 接口要求先登录，否则返回 `401`。

## 测试

```bash
uv run pytest
```

## 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 技术文档

- [docs/README.md](docs/README.md)
- [docs/technical-overview.md](docs/technical-overview.md)
