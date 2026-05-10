# 技术概览

## 1. 当前实现的核心闭环

仓库当前已经打通下面这条最小可用链路：

1. Vue 前端发起登录、导入、列表、播放请求
2. FastAPI 后端负责认证、接口鉴权和业务编排
3. `POST /api/imports` 先创建 `queued` 任务，再由后台 worker 异步处理
4. 导入服务读取 Windows 主机本地视频路径
5. 使用 `ffprobe` 读取媒体元数据
6. 创建 `videos` / `import_jobs` / `video_segments` 记录
7. 按固定大小切片并用 AES-256-GCM 加密
8. 分片先落到本地 staging 目录
9. 在可信主机本地生成可读的 `manifest.json`
10. 上传远端对象时，对目录名、分片文件名和 manifest 内容再做一层远端元信息保护
11. 前端轮询导入任务进度，拿到完成后的 `video_id`
12. 浏览器播放时通过 `/api/videos/{id}/stream` 请求原始字节流
13. 后端优先读本地 staging；缺失时回退到远端对象；仍不可用时再回退到源文件

## 2. 当前技术栈

### 后端

- Python 3.12
- FastAPI
- Starlette SessionMiddleware
- SQLite（标准库 `sqlite3`）
- `ffprobe` / `ffmpeg`
- `cryptography`（AES-256-GCM）
- `httpx`（百度 OpenAPI 调用）

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Axios

## 3. 当前存储架构

当前存储层有两个 backend：

- `mock`
  - 本地目录模拟远端对象存储
  - 主要用于自动化测试和离线开发
- `baidu`
  - 基于百度官方上传 / 查询 / 下载接口
  - 当前已经具备最小可用链路

服务层统一只依赖抽象接口，不直接写百度 HTTP 细节。

## 4. 当前最重要的边界

### 4.1 前端 / 后端边界

- 前端只做 UI、交互、状态展示
- 后端负责认证、导入、加密、存储、回放
- 浏览器不参与分片解密

### 4.2 服务层 / 仓储层边界

- 仓储层只处理 SQLite 读写
- 服务层负责导入、上传、授权、回放等业务流程
- 路由层只做参数收发和 HTTP 语义

### 4.3 本地 staging / 远端对象边界

当前有两份核心密文数据位置：

- 本地 staging：导入后立即可播、便于调试
- 远端对象：mock 目录或百度网盘

回放优先级：

1. 本地 staging
2. 当前配置的 storage backend
3. 源文件回退

## 5. 当前模块职责

### `src/app/core/`

- 环境变量读取
- 路径解析
- Session 密码校验
- 本地内容密钥读写

### `src/app/repositories/`

- `folders`
- `videos`
- `video_segments`
- `import_jobs`
- `settings`

### `src/app/media/`

- `probe.py`：`ffprobe` 探测
- `covers.py`：`ffmpeg` 抽封面
- `chunker.py`：固定大小切片
- `crypto.py`：分片加解密
- `range_map.py`：把 HTTP Range 映射到一个或多个分片

### `src/app/storage/`

- `base.py`：存储契约
- `mock.py`：本地目录模拟远端对象
- `baidu_api.py`：百度 OpenAPI HTTP 调用
- `baidu.py`：StorageBackend 适配层
- `factory.py`：按配置选择 backend

### `src/app/services/`

- `imports.py`：导入、切片、加密、manifest、上传
- `import_worker.py`：后台导入队列与线程 worker
- `streaming.py`：Range 解析、分片读取、解密拼装、回退
- `settings.py`：公开设置读取和更新
- `baidu_oauth.py`：授权链接生成、授权码换 refresh token
- `manifests.py`：manifest 组装、远端路径混淆、远端 manifest 加解密

## 6. 当前百度接入方式

当前百度接入只实现了**后台需要的最小功能集**：

- 生成授权地址
- 用授权码换 refresh token
- 用 refresh token 刷 access token
- `precreate` + `superfile2` + `create` 上传对象
- `list` + `filemetas` + `dlink` 下载对象
- 基础重试与退避
- 真实百度 smoke CLI 与一次在线验收

这保证了：

- 导入上传链路可以切到真实百度 backend
- 播放回退链路可以切到真实百度 backend
- 远端 sync 可以在另一套本地数据库里重建 catalog

## 7. 当前远端元信息保护策略

为了避免百度网盘侧直接暴露业务含义，当前远端对象不再使用明文名字：

- 不再出现明文 `videos/`
- 不再出现明文 `segments/`
- 不再出现明文 `manifest.json`
- 不再出现明文 `000000.cspseg`

当前做法：

1. 使用内容密钥对 `video_id` / `segment_index` / 角色标签做 HMAC-SHA256
2. 截取十六进制摘要前缀，生成稳定但不可读的目录名和文件名
3. 把 manifest JSON 本体再用 AES-256-GCM 加密，上传成二进制 payload

这样另一台可信主机只要拥有相同内容密钥，就仍然可以：

- 推导远端 manifest 文件名
- 扫描远端目录
- 下载并解密 manifest
- 重建 `videos` 与 `video_segments`

## 8. 当前阶段为什么仍保留源文件回退

虽然现在已经有：

- 本地加密分片
- mock / baidu 远端对象

但当前仍保留源文件回退，因为它有两个现实价值：

1. 当远端链路尚未完全稳定时，播放器仍可工作
2. 当授权或远端对象不可用时，开发排障更直接

这只是当前阶段的过渡策略，不代表最终上线形态。

## 9. 当前未完成部分

- 本地加密分片缓存 LRU
- 导入断点续传 / 恢复
- 更细粒度的百度错误分类与长时退避
- 分片并发上传策略
- 远端封面同步
- 前端单元测试和 E2E
