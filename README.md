# Cloud Storage Player

这是一个运行在 Windows 主机上的局域网视频服务：主机负责导入本地视频、按固定大小切片、AES-256-GCM 加密、写入本地元数据，并把加密分片与 manifest 上传到配置的存储后端；浏览器侧通过普通 `video` 标签访问后端 Range 流。

当前仓库已经切到**前后端分离**：

- 后端：FastAPI + SQLite + 服务层 / 仓储层
- 前端：Vue 3 + TypeScript + Vite

## 当前已实现

- UV 管理 Python 项目与依赖
- FastAPI 应用入口与 SQLite bootstrap
- Vue 3 + TypeScript + Vite 前端工程
- 基于 Cookie Session 的单密码认证
- `/api/auth/*`、目录、视频详情、设置、导入接口
- 本地主机路径导入
- `ffprobe` 媒体探测
- 固定大小切片与 AES-256-GCM 加密
- `video_segments` 元数据落库
- 本地 manifest 生成
- 导入时将 manifest / 加密分片上传到**可切换存储后端**
- 默认 `mock` 存储后端（本地目录模拟远端对象存储）
- 播放流优先读取本地加密分片，其次回退到 mock 远端对象，最后才回退到源文件
- `ffmpeg` 封面抽取与 `/covers/*` 静态访问
- `uv run pytest` 自动化测试
- `frontend` 构建通过

## 当前仍未实现

- 真实百度网盘 open platform 接入
- 真实远端 manifest 扫描 / 同步
- 断点续传、后台异步导入、LRU 分片缓存

## Python 版本

项目当前目标版本为 `Python 3.12`。

## 快速开始

### 后端

```bash
uv sync --dev
uv run cloud-storage-player
```

默认监听：

- Host: `0.0.0.0`
- Port: `8000`

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 环境变量

统一使用 `CSP_` 前缀，可放在 `.env` 中。

### 基础配置

- `CSP_APP_NAME`
- `CSP_HOST`
- `CSP_PORT`
- `CSP_SESSION_SECRET`
- `CSP_PASSWORD`
- `CSP_PASSWORD_HASH`
- `CSP_DATABASE_PATH`

### 媒体处理与本地文件

- `CSP_FFPROBE_BINARY`
- `CSP_FFMPEG_BINARY`
- `CSP_COVERS_PATH`
- `CSP_CONTENT_KEY_PATH`
- `CSP_SEGMENT_STAGING_PATH`
- `CSP_SEGMENT_SIZE_BYTES`

### 前后端联调

- `CSP_CORS_ALLOWED_ORIGINS_RAW`

### 存储后端

- `CSP_STORAGE_BACKEND`
  - 当前默认：`mock`
  - 预留：`baidu`
- `CSP_MOCK_STORAGE_PATH`
  - 当前默认：`data/mock-remote`
  - 用于把“远端对象”映射到本地目录，便于离线开发和测试

## 当前接口

认证：

- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`

目录与播放：

- `GET /api/folders`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `GET /api/videos/{video_id}/stream`

导入：

- `POST /api/imports`
- `GET /api/imports`
- `GET /api/imports/{job_id}`

设置：

- `GET /api/settings`
- `POST /api/settings`

## 测试与验证

后端测试：

```bash
uv run pytest
```

前端构建：

```bash
cd frontend
npm run build
```

如果你在项目 `tmp/` 目录放了测试视频，例如 `tmp/rieri.mp4`，可以在服务启动后通过 `POST /api/imports` 手工导入验证。

## 技术文档

- [docs/README.md](docs/README.md)
- [docs/technical-overview.md](docs/technical-overview.md)
- [docs/storage-backend-and-remote-fallback.md](docs/storage-backend-and-remote-fallback.md)
