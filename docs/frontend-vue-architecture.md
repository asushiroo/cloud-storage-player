# Vue 前端架构

## 技术栈

当前前端使用：

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Axios

## 目录结构

- `frontend/src/main.ts`
  - 应用入口
- `frontend/src/router/`
  - 路由与登录守卫
- `frontend/src/stores/`
  - Pinia 状态
- `frontend/src/api/`
  - API 调用封装
- `frontend/src/views/`
  - 路由级页面
- `frontend/src/components/`
  - 复用组件
- `frontend/src/types/`
  - TypeScript 类型

## 当前页面

### 1. 登录页

- 调用 `/api/auth/login`
- 登录成功后跳转媒体库

### 2. 媒体库页

- 读取目录列表
- 读取视频列表
- 读取导入任务
- 提交本地主机路径导入

### 3. 视频详情页

- 读取 `/api/videos/{id}`
- 展示基础元数据
- 直接消费 `/api/videos/{id}/stream`
- 当前已接通后端播放器链路

### 4. 设置页

- 读取 `/api/settings`
- 更新 `/api/settings`

## API 分层原则

前端 API 统一放在 `src/api/`，当前主要包括：

- `auth.ts`
- `library.ts`
- `imports.ts`
- `settings.ts`

统一 HTTP 客户端在 `src/api/http.ts` 中处理：

- `baseURL`
- `withCredentials`
- 资源 URL 拼接

## 当前与后端的协作边界

前端知道的只是：

- 视频列表和详情 JSON
- 导入任务 JSON
- 设置 JSON
- 播放流 URL

前端**不需要知道**：

- 分片如何加密
- 分片是否来自本地 staging
- 是否从 mock 远端回退
- 内容密钥在哪里

这些细节全部由后端处理。

## 当前还没有做的前端能力

- 任务自动轮询刷新
- 更细的错误码统一处理
- 前端单元测试 / E2E
- 更完整的播放器状态 UI
- 组件库与设计系统

## 为什么当前不引入更重方案

当前没有引入 Nuxt、SSR、组件库或更重状态框架，原因很直接：

1. 当前核心风险在后端导入/加密/回放链路
2. 页面数量还不多
3. 先把 API 契约稳定下来更重要
