# Cloud Storage Player

这是一个运行在 Windows 主机上的局域网视频服务：主机负责导入本地视频、按固定大小切片、AES-256-GCM 加密、写入本地元数据，并把加密分片与 manifest 上传到配置的存储后端；浏览器侧通过普通 `video` 标签访问后端 Range 流。

当前仓库采用**前后端分离**：

- 后端：FastAPI + SQLite + 服务层 / 仓储层 / 存储抽象
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
- 存储后端抽象
- `mock`：本地目录模拟远端对象存储
  - `baidu`：基于百度网盘官方 open platform 的最小可用 backend
- 百度 OAuth 授权码换取 refresh token，并缓存 access token
- 导入时把 manifest / 加密分片上传到当前配置的存储后端
- 后台异步导入任务（API 入队，后台 worker 执行）
- 前端导入任务自动轮询与进度展示
- 前端视觉重构（参考 `third/Kyoo` 的卡片 / Hero / 胶囊标签风格，保留 Vue 技术栈）
- 视频自定义标签
  - 导入时可填写标签
  - 视频详情页可编辑标签
  - 标签持久化到本地数据库
  - 标签写入远端加密 manifest，sync 后可恢复
- 媒体库标签/关键词过滤
  - 支持按标题、源路径、标签关键词搜索
  - 支持按单个标签快速过滤
- 远端 manifest 扫描 / catalog sync
- 远端元信息加密
  - 远端视频目录名改为基于内容密钥的稳定混淆名
  - 远端分片文件名改为基于内容密钥的稳定混淆名
  - 远端 manifest 改为 AES-256-GCM 加密后的二进制 payload
  - sync 兼容历史明文 manifest 与新加密 manifest
- 百度 OpenAPI / PCS 的基础重试与退避
- 播放流优先读取本地加密分片，其次回退到远端对象，最后回退到源文件
- 真实百度链路 smoke CLI（上传 / 远端 sync / 远端回放校验）
- 已完成一次真实百度链路在线验收（`tmp/rieri.mp4` 上传 / sync / 远端回放通过）
- `ffmpeg` 封面抽取与 `/covers/*` 静态访问
- `uv run pytest` 自动化测试
- `frontend` 构建通过

## 当前仍未完成

- 新环境首次接入百度时，仍需要管理员手工完成一次 OAuth 授权码流程
- 导入断点续传、LRU 分片缓存
- 更完整的百度错误分类、长时退避与分片并发上传策略
- 远端封面同步与更完整的 catalog 元数据恢复

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

### 存储后端

- `CSP_STORAGE_BACKEND`
  - 当前默认：`mock`
  - 可选：`mock` / `baidu`
- `CSP_MOCK_STORAGE_PATH`
  - 当前默认：`data/mock-remote`
- `CSP_BAIDU_OAUTH_REDIRECT_URI`
  - 当前默认：`oob`
  - 用于百度 OAuth 授权码回调参数

### 前后端联调

- `CSP_CORS_ALLOWED_ORIGINS_RAW`

### 百度网盘开放平台凭据

这些值按项目约定来自**不带 `CSP_` 前缀**的环境变量：

- `BAIDU_APP_KEY`
- `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY`

说明：

- 当前上传 / 下载链路实际使用 `BAIDU_APP_KEY` 与 `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY` 先保留，后续更深的开放能力接入时可能会用到

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

同步：

- `POST /api/videos/sync`

设置：

- `GET /api/settings`
- `POST /api/settings`
- `POST /api/settings/baidu/oauth`

## 百度授权最小流程

1. 在后端环境里配置 `BAIDU_APP_KEY`、`BAIDU_SECRET_KEY`
2. 打开设置页或调用 `GET /api/settings`
3. 取返回的 `baidu_authorize_url`
4. 在浏览器打开授权页，完成授权
5. 把返回的 `code` 提交到 `POST /api/settings/baidu/oauth`
6. 再把 `storage_backend` 切到 `baidu`

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

真实百度 smoke：

```bash
uv run cloud-storage-player-baidu-smoke
```

如果还没有 refresh token，先按脚本打印的授权链接拿到 `code`，再执行：

```bash
uv run cloud-storage-player-baidu-smoke --oauth-code "你的百度授权码"
```

如果你想直接用 `tmp/rieri.mp4` 跑真实百度链路：

```bash
uv run cloud-storage-player-baidu-smoke --source-path tmp/rieri.mp4
```

如果你在项目 `tmp/` 目录放了测试视频，例如 `tmp/rieri.mp4`，可以在服务启动后通过 `POST /api/imports` 手工导入验证。

## 技术文档

- [docs/README.md](docs/README.md)
- [docs/technical-overview.md](docs/technical-overview.md)
- [docs/storage-backend-and-remote-fallback.md](docs/storage-backend-and-remote-fallback.md)
- [docs/baidu-openapi-integration.md](docs/baidu-openapi-integration.md)
