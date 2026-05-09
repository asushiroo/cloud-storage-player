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

当前前端目录采用：

- `frontend/src/main.ts`
  - Vue 应用入口
- `frontend/src/router/`
  - 路由定义与登录守卫
- `frontend/src/stores/`
  - Pinia 状态管理
- `frontend/src/api/`
  - 后端 API 调用封装
- `frontend/src/views/`
  - 路由级页面
- `frontend/src/components/`
  - 复用组件
- `frontend/src/types/`
  - TypeScript API 类型

## 当前页面

### 1. 登录页

- 通过 `/api/auth/login` 登录
- 登录成功后跳到媒体库

### 2. 媒体库页

- 读取目录列表
- 读取视频列表
- 读取导入任务
- 提交本地导入任务

### 3. 视频详情页

- 读取 `/api/videos/{id}`
- 展示基础元数据
- 为后续播放页留下位置

### 4. 设置页

- 读取 `/api/settings`
- 更新 `/api/settings`

## 状态管理策略

当前前端只把“跨页面共享且业务相关”的状态放入 Pinia。

目前主要是：

- 登录态

页面自身的局部状态，如：

- 表单输入
- 当前 loading
- 当前错误消息

依然放在各自页面组件里，不提前抽象。

## API 分层原则

前端 API 调用集中放在 `src/api/`：

- `auth.ts`
- `library.ts`
- `imports.ts`
- `settings.ts`

统一 HTTP 客户端在：

- `src/api/http.ts`

这里统一处理：

- `baseURL`
- `withCredentials`
- 资源 URL 拼接

## 路由守卫

当前使用全局路由守卫：

1. 页面切换前先检查 Session 状态
2. 未登录访问受保护页时跳到 `/login`
3. 已登录访问 `/login` 时跳回媒体库

这样可以让前端路由与后端 Session 保持一致。

## 当前没有做的前端能力

还没有实现：

- 播放器页面与真实流接口接通
- 任务轮询刷新策略
- 错误码统一拦截
- UI 组件库
- 国际化
- 单元测试 / E2E 测试

这些都可以后续逐步补，而不需要现在先做复杂框架。

## 开发启动方式

前端建议命令：

```bash
cd frontend
npm install
npm run dev
```

如果后端不在默认地址，需要设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 为什么当前不引入更重的前端方案

当前没有引入 Nuxt、SSR、组件库或复杂状态框架，原因很简单：

1. 项目第一阶段重点仍在后端导入/加密/回放链路
2. 当前页面数量不多
3. 先把 API 契约和页面骨架稳定下来更重要

等播放页、任务页、设置页复杂度继续上升时，再决定是否需要更重的前端工程能力。
