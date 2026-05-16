# 前端架构（React）

## 技术栈

当前前端使用：

- React
- TypeScript
- Vite
- React Router
- TanStack Query

## 目录结构

- `frontend/src/main.tsx`
  应用入口
- `frontend/src/App.tsx`
  路由定义
- `frontend/src/api/`
  后端 API 调用封装
- `frontend/src/pages/`
  路由级页面
- `frontend/src/components/`
  通用组件
- `frontend/src/hooks/`
  会话与共享逻辑
- `frontend/src/types/`
  前后端契约类型
- `frontend/src/utils/`
  纯工具函数

## 当前页面职责

### 登录页

- 调用 `/api/auth/login`
- 恢复或校验当前 session

### 推荐页

- 读取推荐数据
- 展示 3D Banner、最近观看、次推荐位

### 媒体库页

- 读取视频列表
- 支持搜索、标签筛选、分批展开
- 记忆过滤条件与滚动位置

### 视频详情页

- 读取 `/api/videos/{id}`
- 编辑标签
- 管理封面
- 进入播放页

### 播放页

- 直接使用 `/api/videos/{id}/stream`
- 保留原生播放器控件
- 负责点赞、跳高光、观看心跳与推荐联动 UI

### 管理页

- 发起单文件导入或文件夹导入
- 查看后台任务
- 查看与清理缓存
- 发起同步

### 设置页

- 读取 `/api/settings`
- 更新运行设置
- 提交百度 OAuth 授权码
- 当没有授权链接时，提示去 `/admin` 填写百度凭据

## API 协作原则

前端只依赖后端契约，不依赖后端内部实现细节。

前端关心的是：

- 视频列表和详情 JSON
- 导入任务 JSON
- 设置 JSON
- 播放流 URL
- 授权链接与授权状态

前端不关心的是：

- 分片如何加密
- 分片来自本地还是百度
- refresh token 如何持久化
- manifest 如何写入与同步

## 当前实现边界

- 前端主实现已经完全转到 React
- 旧 Vue 方案仅作为历史文档背景，不再是当前运行时
- 播放、推荐、媒体库和管理流程都以 `frontend/` 为准
