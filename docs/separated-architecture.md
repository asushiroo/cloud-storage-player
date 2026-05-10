# 前后端分离架构

## 目标

项目当前采用：

- 后端：FastAPI + SQLite + 服务层 / 仓储层 / 存储抽象
- 前端：Vue 3 + TypeScript + Vite + Pinia + Vue Router

核心原则：

1. 后端负责认证、导入、加密、存储、回放
2. 前端负责页面、交互、状态展示
3. 双方只通过稳定的 HTTP JSON API 协作

## 为什么要前后端分离

这个项目的业务复杂度主要在后端：

- 本地路径导入
- 媒体探测
- 分片加密
- 远端上传
- Range 回放
- 百度 OAuth 与对象下载

而前端会逐步演进出：

- 登录页
- 媒体库页
- 视频详情页
- 导入状态展示
- 设置页

继续把 UI 写在后端模板里会让边界越来越混乱，所以当前已经明确把新 UI 放在 `frontend/`。

## 当前职责拆分

### 后端负责

- Session 认证
- API 鉴权
- 目录 / 视频 / 设置数据
- 本地导入任务
- `ffprobe` / `ffmpeg`
- 分片与 AES-256-GCM 加密
- storage backend 上传与下载
- 百度授权码换 refresh token
- 服务端 Range 解密拼装

### 前端负责

- 登录态页面跳转
- 媒体库列表展示
- 视频详情展示
- 导入表单与任务展示
- 设置页交互
- 百度授权链接展示与授权码提交

## 明确不放进前端的逻辑

- 百度 / mock 存储调用
- 内容密钥管理
- AES-GCM 解密
- 分片 Range 拼装
- 主机文件系统访问

## 当前开发联调方式

- 前端 dev server：`5173`
- 后端 API：`8000`
- 认证方式：后端 Session Cookie

因此后端需要：

- 配置 CORS
- `allow_credentials = true`

前端需要：

- `withCredentials = true`

## 后端内部也做分层

前后端分离之外，后端内部当前还拆成：

- route
- service
- repository
- media
- storage

其中：

- route 只负责 HTTP
- service 负责编排
- repository 只负责 SQLite
- media 只负责媒体处理和 Range 映射
- storage 只负责远端对象读写

这样后续继续演进百度集成时，不需要把上传/下载逻辑重新塞回路由层。
