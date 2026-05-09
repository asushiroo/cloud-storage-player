# 运行与配置

## 运行前提

当前运行依赖：

- Python 3.12
- UV
- Node.js / npm（前端开发时）
- `ffprobe`
- `ffmpeg`（当前主要用于测试或未来封面抽取，不是应用启动硬依赖）

项目使用：

- FastAPI 作为后端 Web 框架
- Vue 3 + Vite 作为前端开发架构
- Starlette `SessionMiddleware` 作为 Session 中间件
- 标准库 `sqlite3` 作为当前阶段数据库访问实现

## 初始化方式

首次执行：

```bash
uv sync --dev
uv run cloud-storage-player
```

前端开发执行：

```bash
cd frontend
npm install
npm run dev
```

启动时会自动执行：

1. 读取环境变量
2. 创建 FastAPI 应用
3. 初始化 SQLite 数据库
4. 创建封面输出目录
5. 注册 Session 中间件
6. 注册 CORS 中间件
7. 挂载 `/covers` 静态目录
8. 注册页面路由、JSON 认证路由、目录路由、导入路由、设置路由

## 环境变量

统一使用 `CSP_` 前缀。

### 基础运行配置

- `CSP_APP_NAME`
  - 默认：`Cloud Storage Player`
- `CSP_HOST`
  - 默认：`0.0.0.0`
- `CSP_PORT`
  - 默认：`8000`

### 认证相关

- `CSP_SESSION_SECRET`
  - 默认：`change-me-before-production`
  - 用于签名 Session Cookie
  - 生产环境必须修改
- `CSP_PASSWORD`
  - 默认：`admin`
  - 当未显式提供密码哈希时，会在启动时被哈希化
- `CSP_PASSWORD_HASH`
  - 如果存在，优先级高于 `CSP_PASSWORD`
  - 格式为：
    - `pbkdf2_sha256$iterations$salt$digest`

### 数据库与工具

- `CSP_DATABASE_PATH`
  - 默认：`data/cloud_storage_player.db`
  - 如果是相对路径，则相对于项目根目录解析
- `CSP_FFPROBE_BINARY`
  - 默认：`ffprobe`
  - 用于覆盖 `ffprobe` 可执行文件路径
- `CSP_FFMPEG_BINARY`
  - 默认：`ffmpeg`
  - 用于覆盖封面抽取使用的 `ffmpeg`
- `CSP_COVERS_PATH`
  - 默认：`data/covers`
  - 用于指定封面输出目录
- `CSP_CONTENT_KEY_PATH`
  - 默认：`data/keys/content.key`
  - 用于指定本地内容加密密钥文件
- `CSP_SEGMENT_STAGING_PATH`
  - 默认：`data/segments`
  - 用于指定本地加密分片暂存目录
- `CSP_SEGMENT_SIZE_BYTES`
  - 默认：`4194304`
  - 用于指定导入时的固定分片大小
- `CSP_CORS_ALLOWED_ORIGINS_RAW`
  - 默认：`http://127.0.0.1:5173,http://localhost:5173`
  - 逗号分隔的前端允许来源列表

## Session 策略

当前 Session 使用 Starlette 的签名 Cookie：

- `same_site = "lax"`
- `https_only = False`

这里 `https_only=False` 只是为了当前开发切片能够直接在本地网络环境跑起来。
如果后续进入真实部署，应至少补上：

- HTTPS 传输
- 更严格的 Cookie 策略
- 密钥轮换策略

## 前端开发模式

当前前端开发模式是：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`

前端通过 `VITE_API_BASE_URL` 指向后端 API。
后端通过 CORS 配置允许前端来源，并启用带凭据请求。

## 静态封面目录

当前导入成功后，如果封面抽取成功，会把 JPG 文件写入本地封面目录，并通过 `/covers/<video_id>.jpg` 访问。

默认映射关系：

- 本地目录：`data/covers`
- URL 前缀：`/covers`

## 当前播放流模式

当前播放流接口已经存在，但还只是过渡实现：

- `GET /api/videos/{video_id}/stream`

当前它直接从本地导入源文件读取字节并返回给浏览器。
这样可以先把：

- 前端播放器
- Cookie 认证
- Range 请求
- 视频详情页

这些链路打通。

后续再把底层数据来源替换成：

- 分片
- 解密
- 百度网盘拉取

## 当前分片与密钥模式

当前导入阶段已经会：

1. 读取本地源文件
2. 按固定大小切成多个分片
3. 用 AES-256-GCM 加密每个分片
4. 将加密结果写入本地 staging 目录
5. 将 nonce、tag、checksum、偏移等元数据写入 SQLite

当前内容密钥保存在本地主机文件中，不会写入远端 manifest。

## 为什么当前不用 ORM

这一步我刻意保留在标准库 `sqlite3` 层：

1. 当前表数量少
2. 查询和写入路径很短
3. 还没进入复杂关联和迁移阶段
4. 先把业务边界跑通，比先引入 ORM 更符合“最小实现”的要求

等后续出现这些需求时，再考虑是否要升级：

- 更复杂的查询组合
- 多阶段迁移
- 更强的事务封装
- 多数据库后端兼容
