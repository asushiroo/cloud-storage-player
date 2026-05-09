# 文档目录

本文档描述的是**当前仓库已经落地的实现**，不是最终完整产品蓝图。

## 推荐阅读顺序

1. [技术总览](technical-overview.md)
2. [前后端分离架构](separated-architecture.md)
3. [Vue 前端架构](frontend-vue-architecture.md)
4. [运行与配置](runtime-and-configuration.md)
5. [存储后端与远端回退](storage-backend-and-remote-fallback.md)
6. [数据库设计](database-schema.md)
7. [HTTP 接口说明](http-api.md)
8. [本地导入与媒体探测](import-and-media-probe.md)
9. [测试与样例数据](testing-and-sample-data.md)

## 当前实现边界

已实现：

- FastAPI 应用启动与 SQLite bootstrap
- 前后端分离骨架
- Vue 前端工程
- Session 登录
- 目录 / 视频详情 / 设置 / 导入接口
- 本地文件导入、`ffprobe` 探测、封面抽取
- 固定大小分片与 AES-256-GCM 加密
- `video_segments` 元数据落库
- 本地 manifest 生成
- manifest / 加密分片上传到默认 mock 存储后端
- 播放流从本地 staging 回退到 mock 远端对象，再回退到源文件

未实现：

- 真实百度网盘 API 接入
- 真实远端目录扫描 / catalog sync
- 导入后台异步化、断点续传、缓存淘汰

所以请把这些文档理解成：**当前阶段技术实现说明**。
