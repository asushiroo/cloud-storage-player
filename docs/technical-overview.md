# 技术概览

## 文档范围

这份文档只总结**当前已经实现的内容**。
更细的技术说明已经拆到多个文件中。

## 当前实现摘要

当前仓库已经具备：

- FastAPI 应用启动
- 前后端分离架构方向
- Vue 前端工程骨架
- Session 登录 / 退出
- `/api/auth/*` JSON 认证接口
- SQLite bootstrap
- `folders` / `videos` / `settings` / `import_jobs`
- 目录列表、视频详情、设置接口
- 本地文件导入接口
- `ffprobe` 媒体探测
- `ffmpeg` 封面抽取
- `/covers` 静态挂载
- 本地源文件流播放接口
- 自动化测试

当前尚未具备：

- 百度网盘接入
- 分片加密
- manifest 生成与同步
- 基于加密分片的播放

## 推荐阅读顺序

1. [文档目录](README.md)
2. [运行与配置](runtime-and-configuration.md)
3. [前后端分离架构](separated-architecture.md)
4. [Vue 前端架构](frontend-vue-architecture.md)
5. [数据库设计](database-schema.md)
6. [HTTP 接口说明](http-api.md)
7. [本地导入与媒体探测](import-and-media-probe.md)
8. [测试与样例数据](testing-and-sample-data.md)

## 当前最值得注意的实现选择

### 1. 先用标准库 `sqlite3`

当前还没有引入 ORM。
这是为了先用最小成本把目录、视频、导入任务和媒体探测链路跑通。

### 2. 导入任务当前是同步的

虽然表结构里已经有 `import_jobs`，但当前 `POST /api/imports` 还是同步执行。
这样可以先稳定：

- 本地路径校验
- 任务状态写入
- `ffprobe` 探测
- 视频元数据落库
- 封面抽取落地

### 3. 文档与代码尽量保持一一对应

这些文档不是未来设计草稿，而是当前实现说明。
如果代码继续演进，文档也应该同步演进。

### 4. 前端新功能不再写进后端模板

当前仍保留少量 Jinja 页面作为兼容层，但新的 UI 功能方向已经切到 `frontend/`。
