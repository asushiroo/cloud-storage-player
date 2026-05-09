# 数据库设计

## 说明

当前数据库是 SQLite，启动时自动初始化。

现阶段它承担的是：

- 登录后目录数据的本地事实来源
- 本地导入任务记录
- 后续百度网盘同步前的基础元数据存储

当前还没有做完整 migration 框架，只做了“启动即建表 + 必要列补齐”的轻量 bootstrap。

## 表：folders

字段：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `name TEXT NOT NULL`
- `cover_path TEXT`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 表示 UI 中的视频分类目录

当前约束：

- 没有唯一索引
- 没有层级结构
- 没有排序字段

这些都还没被当前功能需要，所以暂时不加。

## 表：videos

字段：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL`
- `title TEXT NOT NULL`
- `cover_path TEXT`
- `mime_type TEXT NOT NULL`
- `size INTEGER NOT NULL DEFAULT 0`
- `duration_seconds REAL`
- `manifest_path TEXT`
- `source_path TEXT`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 保存视频基础元数据
- 为未来导入、同步、播放提供最小记录载体

当前字段说明：

- `manifest_path`
  - 用于记录目标 manifest 路径
  - 当前会写入未来的百度网盘目标路径，例如 `/CloudStoragePlayer/videos/1/manifest.json`
- `cover_path`
  - 当前用于保存浏览器可访问的相对 URL
  - 例如：`/covers/1.jpg`
- `source_path`
  - 当前用于记录本地导入源路径
  - 这是一个过渡字段，后续是否长期保留要看导入设计

## 表：video_segments

字段：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE`
- `segment_index INTEGER NOT NULL`
- `original_offset INTEGER NOT NULL`
- `original_length INTEGER NOT NULL`
- `ciphertext_size INTEGER NOT NULL`
- `plaintext_sha256 TEXT NOT NULL`
- `nonce_b64 TEXT NOT NULL`
- `tag_b64 TEXT NOT NULL`
- `cloud_path TEXT`
- `local_staging_path TEXT`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 保存每个视频分片的加密元数据
- 为后续云上传、manifest 生成、分片回放映射做准备

当前字段说明：

- `cloud_path`
  - 当前会预先写入未来的百度网盘目标分片路径
  - 例如 `/CloudStoragePlayer/videos/1/segments/000000.cspseg`
- `local_staging_path`
  - 当前指向本地主机上的已加密分片文件
  - 这是过渡阶段的本地暂存能力

## 表：settings

字段：

- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 存储本地设置项
- 为未来 Baidu root、refresh token 元数据等配置落地做准备

当前状态：

- 已有仓储层
- 已有 HTTP 设置接口
- 当前暴露的是非敏感公开配置

## 表：import_jobs

字段：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `source_path TEXT NOT NULL`
- `folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL`
- `requested_title TEXT`
- `status TEXT NOT NULL`
- `progress_percent INTEGER NOT NULL DEFAULT 0`
- `error_message TEXT`
- `video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 记录本地导入任务的状态变化

当前状态机：

- `queued`
- `running`
- `completed`
- `failed`

当前实现特点：

- 导入是同步执行的
- API 返回时任务通常已经处于 `completed` 或 `failed`
- 这不是最终方案，只是为了先把导入路径、状态记录和媒体探测打通
- 当前导入成功后还会尽力抽取一张封面，但封面失败不会让导入任务失败
- 当前导入成功后还会生成本地加密分片与 `video_segments` 元数据

## 启动时的 schema bootstrap

当前 `initialize_database()` 做两类事情：

1. `CREATE TABLE IF NOT EXISTS`
2. 对已存在旧表执行必要列补齐

目前已补齐的列：

- `videos.source_path`

这是为了避免在本地已有旧数据库时，因为新增字段导致应用直接报错。

## 当前没有做的数据库能力

还没有实现：

- 版本化 migration
- 索引调优
- 审计字段统一封装
- 批量事务服务层
- 数据清理策略

这些需要等到导入、同步、播放逻辑稳定后再补，避免过早设计。
