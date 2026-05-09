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
9. 再把 manifest 与加密分片上传到配置的存储后端
10. 浏览器播放时通过 `/api/videos/{id}/stream` 请求原始字节流
11. 后端优先读本地 staging；缺失时回退到 mock 远端对象；仍不可用时再回退到源文件

## 2. 当前技术栈

### 后端

- Python 3.12
- FastAPI
- Starlette SessionMiddleware
- SQLite（标准库 `sqlite3`）
- `ffprobe` / `ffmpeg`
- `cryptography`（AES-256-GCM）

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Axios

## 3. 为什么当前要先做 mock 存储后端

真实百度网盘接入还没有完成，但导入和播放链路已经需要“远端对象”这个边界。

所以当前先把后端拆成：

- 存储契约 `storage/base.py`
- 默认本地模拟实现 `storage/mock.py`
- 工厂 `storage/factory.py`
- 预留的 `storage/baidu.py`

这样做的价值是：

1. 服务层先依赖抽象，不直接耦合某个云 SDK
2. 自动化测试可以稳定验证“上传后再回放”的完整链路
3. 后续换成百度实现时，导入/播放服务只需要换 backend，不需要重写业务流程

## 4. 当前最重要的边界

### 4.1 前端 / 后端边界

- 前端只做 UI、交互、状态展示
- 后端负责认证、导入、加密、存储、流式回放
- 浏览器不参与分片解密

### 4.2 服务层 / 仓储层边界

- 仓储层只处理 SQLite 读写
- 服务层负责导入、上传、回放等业务流程
- 路由层只做参数收发和 HTTP 语义

### 4.3 本地 staging / 远端对象边界

当前有两份加密分片位置：

- 本地 staging：便于导入后立即可播，也方便调试
- mock 远端对象：模拟未来百度网盘中的远端分片

回放优先级：

1. 本地 staging
2. mock 远端对象
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

全部保持轻量，不掺杂媒体处理和云存储逻辑。

### `src/app/media/`

- `probe.py`：`ffprobe` 探测
- `covers.py`：`ffmpeg` 抽封面
- `chunker.py`：固定大小切片
- `crypto.py`：分片加解密
- `range_map.py`：把 HTTP Range 映射到一个或多个分片

### `src/app/storage/`

- `base.py`：存储契约
- `mock.py`：本地目录模拟远端对象
- `factory.py`：按配置选择 backend
- `baidu.py`：预留占位

### `src/app/services/`

- `imports.py`：导入、切片、加密、manifest、上传
- `manifests.py`：manifest 组装与路径约定
- `streaming.py`：Range 解析、分片读取、解密拼装、回退
- `settings.py`：公开设置读取和更新

## 6. 当前阶段为什么仍保留源文件回退

虽然现在已经有：

- 本地加密分片
- mock 远端对象

但当前仍保留源文件回退，因为它有两个现实价值：

1. 当内容密钥或分片链路异常时，开发阶段更容易定位问题
2. 在真实百度接入前，可以保证最小播放器链路始终可用

这只是当前阶段的过渡策略，不代表最终上线形态。

## 7. 当前未完成部分

- 真实百度网盘 OAuth / 上传 / 下载
- 远端 manifest 扫描与 catalog sync
- 导入后台任务化
- 本地加密分片缓存 LRU
- 前端单元测试和 E2E
