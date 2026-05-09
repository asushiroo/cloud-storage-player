# 文档目录

本文档目录描述的是**当前已经落地的实现**，不是最终完整产品说明。

## 文档索引

- [技术总览](technical-overview.md)
- [前后端分离架构](separated-architecture.md)
- [Vue 前端架构](frontend-vue-architecture.md)
- [运行与配置](runtime-and-configuration.md)
- [数据库设计](database-schema.md)
- [HTTP 接口说明](http-api.md)
- [本地导入与媒体探测](import-and-media-probe.md)
- [测试与样例数据](testing-and-sample-data.md)

## 当前实现边界

已实现：

- FastAPI 应用启动
- 前后端分离骨架
- Vue 前端目录
- Session 登录
- SQLite 基础表
- 目录 / 视频 / 设置接口
- 本地文件导入任务（同步实现）
- `ffprobe` 媒体探测
- 导入时封面抽取
- `/covers/*` 静态文件访问

未实现：

- 百度网盘客户端
- 分片加密
- manifest 上传 / 同步
- Range 播放

所以阅读这些文档时，请把它们理解成“当前实现说明”，而不是最终产品手册。
