# 技术概览

## 1. 当前实现的核心闭环

仓库当前已经打通下面这条最小可用链路：

1. Vue 前端发起登录、导入、列表、播放请求
2. FastAPI 后端负责认证、接口鉴权和业务编排
3. 导入服务读取 Windows 主机本地视频路径
4. 使用 `ffprobe` 读取媒体元数据
5. 创建 `videos` / `import_jobs` / `video_segments` 记录
6. 按固定大小切片并用 AES-256-GCM 加密
7. 分片先落到本地 staging 目录
8. 生成本地 `manifest.json`
9. 把 manifest 与加密分片上传到当前配置的存储后端
10. 浏览器播放时通过 `/api/videos/{id}/stream` 请求原始字节流
11. 后端优先读本地 staging；缺失时回退到远端对象；仍不可用时再回退到源文件

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
- `streaming.py`：Range 解析、分片读取、解密拼装、回退
- `settings.py`：公开设置读取和更新
- `baidu_oauth.py`：授权链接生成、授权码换 refresh token
- `manifests.py`：manifest 组装与路径约定

## 6. 当前百度接入方式

当前百度接入只实现了**后台需要的最小功能集**：

- 生成授权地址
- 用授权码换 refresh token
- 用 refresh token 刷 access token
- `precreate` + `superfile2` + `create` 上传对象
- `list` + `filemetas` + `dlink` 下载对象

这保证了：

- 导入上传链路可以切到真实百度 backend
- 播放回退链路可以切到真实百度 backend

## 7. 当前阶段为什么仍保留源文件回退

虽然现在已经有：

- 本地加密分片
- mock / baidu 远端对象

但当前仍保留源文件回退，因为它有两个现实价值：

1. 当远端链路尚未完全稳定时，播放器仍可工作
2. 当授权或远端对象不可用时，开发排障更直接

这只是当前阶段的过渡策略，不代表最终上线形态。

## 8. 当前未完成部分

- 真实百度链路的自动化在线验收
- 远端 manifest 扫描与 catalog sync
- 导入后台任务化
- 本地加密分片缓存 LRU
- 上传 / 下载重试与限流退避
- 前端单元测试和 E2E
