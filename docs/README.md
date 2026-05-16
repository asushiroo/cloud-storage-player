# 技术文档索引

这里记录的是仓库当前已经落地的实现。

## 建议阅读顺序

1. [技术总览](technical-overview.md)
2. [前后端分离架构](separated-architecture.md)
3. [前端架构（React）](frontend-vue-architecture.md)
4. [运行与配置](runtime-and-configuration.md)
5. [数据库设计](database-schema.md)
6. [HTTP 接口说明](http-api.md)
7. [本地导入与媒体探测](import-and-media-probe.md)
8. [存储后端与远端回退](storage-backend-and-remote-fallback.md)
9. [百度网盘 OpenAPI 接入](baidu-openapi-integration.md)
10. [测试与样例数据](testing-and-sample-data.md)

## 当前重点

- 前端主实现位于 `frontend/`，技术栈为 React + TypeScript + Vite
- `/admin` 是后端管理员页面，负责主机侧配置与密码管理
- `/settings` 是前端运行设置页，负责缓存目录、并发、后端类型和百度授权流程
- 百度 App Key / Secret Key 不再只能依赖环境变量，也可以通过 `/admin` 保存到本地设置
