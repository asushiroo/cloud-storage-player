# Cloud Storage Player 🎬

一个运行在 Windows 主机上的局域网私人视频库。

它负责把本地视频导入、切片、加密并保存到本地或百度网盘，再由后端把原始视频字节流安全地回放给局域网内的浏览器。浏览器侧只需要普通网页和原生 `video` 播放能力，不参与解密。

## ✨ 主要功能

- Windows 主机本地视频导入
- AES-256-GCM 加密分片存储
- 本地 `mock` 存储与百度网盘存储双后端
- 局域网网页访问、登录、浏览、播放
- 推荐页、媒体库、详情页、管理页、设置页
- 后端 `/admin` 管理员页面，可填写首次启动所需的关键配置
- 后端统一处理播放 Range、远端回退、封面读取与同步

## 🧱 设计理念

- 后端是唯一事实来源：导入、加密、manifest、同步、播放都由后端负责
- 前后端分离：前端专注 UI 与交互，后端专注媒体和存储链路
- Windows 优先：以主机侧部署和非程序员可使用为目标
- 低耦合：尽量按职责拆分模块，避免大而混杂的实现

## 🚀 快速开始

### 1. 准备环境

- Python `3.12`
- UV
- Node.js / npm
- `FFmpeg` 与 `FFprobe`

项目根目录中的 `.python-version` 目标为：

```text
3.12
```

### 2. 安装依赖

```bash
uv sync --dev
npm install
```

### 3. 启动开发环境

后端：

```bash
uv run cloud-storage-player
```

前端：

```bash
npm run dev
```

默认入口：

- 前端开发页：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- 管理员页面：`http://127.0.0.1:8000/admin`

## ⚙️ 首次使用

首次使用时，建议按这个顺序：

1. 启动后端服务
2. 打开 `/admin`
3. 填写管理员密码、百度 App Key / Secret Key、会话密钥等主机侧配置
4. 再到前端 `/settings` 页面完成运行参数与百度授权码流程

说明：

- 百度 OAuth 授权码流程仍需管理员手工完成一次
- `session_secret` 这类启动级配置保存后需要重启服务生效

## 🗂️ 目录结构

- `src/`
  FastAPI 后端、导入/加密/存储/播放逻辑
- `frontend/`
  React + TypeScript + Vite 前端
- `docs/`
  技术文档
- `third/`
  参考代码，不参与当前运行时

## 🧪 常用验证

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

## 📚 文档

- [技术文档索引](docs/README.md)
- [技术总览](docs/technical-overview.md)
- [运行与配置](docs/runtime-and-configuration.md)
- [HTTP 接口](docs/http-api.md)
