# 运行与配置

## 1. 运行前提

当前开发/测试环境依赖：

- Python 3.12
- UV
- Node.js / npm（前端开发）
- `ffprobe`
- `ffmpeg`

项目当前采用：

- 后端：FastAPI
- 前端：Vue 3 + Vite
- 数据库：SQLite
- 密钥管理：本地文件
- 存储后端：`mock` / `baidu`

## 2. UV 初始化方式

### 后端

```bash
uv sync --dev
uv run cloud-storage-player
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 3. 启动时会做什么

后端启动后会依次执行：

1. 读取环境变量与 `.env`
2. 初始化 FastAPI 应用
3. 初始化 SQLite schema
4. 创建本地封面目录
5. 注册 SessionMiddleware
6. 注册 CORS
7. 挂载 `/covers`
8. 注册认证、目录、导入、设置、播放路由

当前 mock 存储目录不要求启动前预创建；首次上传时会自动创建。

## 4. 环境变量

统一使用 `CSP_` 前缀，除非特别说明。

### 4.1 基础运行配置

- `CSP_APP_NAME`
  - 默认：`Cloud Storage Player`
- `CSP_HOST`
  - 默认：`0.0.0.0`
- `CSP_PORT`
  - 默认：`8000`

### 4.2 认证配置

- `CSP_SESSION_SECRET`
  - 默认：`change-me-before-production`
  - 生产环境必须修改
- `CSP_PASSWORD`
  - 默认：`admin`
- `CSP_PASSWORD_HASH`
  - 如果存在，优先于明文密码配置

### 4.3 数据库与媒体工具

- `CSP_DATABASE_PATH`
  - 默认：`data/cloud_storage_player.db`
- `CSP_FFPROBE_BINARY`
  - 默认：`ffprobe`
- `CSP_FFMPEG_BINARY`
  - 默认：`ffmpeg`

### 4.4 本地文件路径

- `CSP_COVERS_PATH`
  - 默认：`data/covers`
- `CSP_CONTENT_KEY_PATH`
  - 默认：`data/keys/content.key`
- `CSP_SEGMENT_STAGING_PATH`
  - 默认：`data/segments`
- `CSP_MOCK_STORAGE_PATH`
  - 默认：`data/mock-remote`

这些路径如果传入相对路径，都会按**项目根目录**解析。

### 4.5 分片与存储配置

- `CSP_SEGMENT_SIZE_BYTES`
  - 默认：`4194304`
  - 即 `4 MiB`
- `CSP_STORAGE_BACKEND`
  - 默认：`mock`
  - 当前支持值：
    - `mock`
    - `baidu`
- `CSP_BAIDU_OAUTH_REDIRECT_URI`
  - 默认：`oob`
  - 当前用于授权码回填流程

### 4.6 百度网盘开放平台配置

这些变量**不带 `CSP_` 前缀**：

- `BAIDU_APP_KEY`
- `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY`

当前实际代码路径里：

- OAuth 与存储 backend 已经使用 `BAIDU_APP_KEY` / `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY` 暂时保留给后续更深的开放能力接入

### 4.7 前后端联调配置

- `CSP_CORS_ALLOWED_ORIGINS_RAW`
  - 默认：`http://127.0.0.1:5173,http://localhost:5173`

## 5. Session 策略

当前 Session 使用 Starlette 的签名 Cookie：

- `same_site = "lax"`
- `https_only = False`

这是为了当前局域网开发和测试切片能快速跑通。
未来部署时至少需要补：

- HTTPS
- 更严格 Cookie 策略
- 密钥轮换

## 6. 前后端开发模式

默认本地联调：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`

前端通过：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

指向后端 API。

## 7. 当前存储后端模式

### 7.1 mock backend

当 `storage_backend=mock` 时：

- 远端对象不会发到真实云
- 会按“远端路径”映射到 `CSP_MOCK_STORAGE_PATH` 下的本地文件

例如：

- 远端路径：`/apps/CloudStoragePlayer/<opaque_video_dir>/<opaque_manifest>.bin`
- 本地映射：`data/mock-remote/apps/CloudStoragePlayer/<opaque_video_dir>/<opaque_manifest>.bin`

说明：

- `<opaque_video_dir>`、`<opaque_manifest>`、`<opaque_segment>` 都是基于内容密钥稳定推导的混淆名
- 因此 mock backend 目录现在也不会直接出现 `videos/12/manifest.json` 这种明文元信息

### 7.2 baidu backend

当 `storage_backend=baidu` 时：

- 后端会从本地 SQLite 读取 refresh token
- 再通过 `BAIDU_APP_KEY` / `BAIDU_SECRET_KEY` 刷新 access token
- 导入时会调用百度官方上传接口
- 回放时会调用百度官方查询 / 下载接口
- 远端 sync 时需要同一份 `content.key` 才能发现并解密新格式 manifest

当前默认 `baidu_root_path` 是：

- `/apps/CloudStoragePlayer`

## 8. 当前播放流模式

播放接口：

- `GET /api/videos/{video_id}/stream`

当前读取优先级：

1. 本地加密分片 staging
2. 当前配置的 storage backend
3. 本地源文件

只要内容密钥可用，后端就会在服务端解密并返回浏览器需要的原始字节。

## 9. 当前导入落地产物

一次成功导入会产生这些产物：

### 本地数据库

- `videos`
- `video_segments`
- `import_jobs`
- `settings`

### 本地文件

- `data/segments/<video_id>/segments/*.cspseg`
- `data/segments/<video_id>/manifest.json`
- `data/segments/<video_id>/manifest.remote.bin`
- `data/covers/<video_id>.jpg`（如果封面抽取成功）
- `data/keys/content.key`

### mock 远端对象（当 backend=mock）

- `data/mock-remote/apps/CloudStoragePlayer/<opaque_video_dir>/<opaque_manifest>.bin`
- `data/mock-remote/apps/CloudStoragePlayer/<opaque_video_dir>/<opaque_segment>.bin`

### 百度远端对象（当 backend=baidu）

- `/apps/CloudStoragePlayer/<opaque_video_dir>/<opaque_manifest>.bin`
- `/apps/CloudStoragePlayer/<opaque_video_dir>/<opaque_segment>.bin`

## 10. 推荐验证命令

后端测试：

```bash
uv run pytest
```

前端构建：

```bash
cd frontend
npm run build
```
