# 数据库设计

## 说明

当前数据库使用 SQLite，启动时自动初始化。

它现在承担三类职责：

1. 作为本地目录与视频元数据事实来源
2. 记录导入任务状态
3. 记录分片元数据、远端对象逻辑路径与授权状态

当前仍然没有独立 migration 框架，而是采用：

- `CREATE TABLE IF NOT EXISTS`
- 启动时补齐必要列

这是当前阶段刻意保持简单的选择。

## 表：folders

字段：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `name TEXT NOT NULL`
- `cover_path TEXT`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 表示前端媒体库中的目录分类

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

字段说明：

- `manifest_path`
  - 保存远端 manifest 的逻辑路径
  - 当前默认会写成 `/apps/CloudStoragePlayer/videos/<id>/manifest.json`
- `source_path`
  - 保存最初导入时的主机本地源文件路径
  - 当前阶段仍用于最后一层播放回退
- `cover_path`
  - 保存浏览器可访问路径，例如 `/covers/12.jpg`

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

字段说明：

- `cloud_path`
  - 远端分片逻辑路径
  - 当前默认格式：`/apps/CloudStoragePlayer/videos/<id>/segments/000000.cspseg`
- `local_staging_path`
  - 本地已加密分片暂存文件路径
  - 播放时会优先读取这里
- `plaintext_sha256`
  - 当前用于记录加密前明文摘要，便于后续校验与调试

## 表：settings

字段：

- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

用途：

- 存储公开本地设置项
- 存储百度授权后的 refresh token

当前已使用的 key 包括：

- `baidu_root_path`
- `cache_limit_bytes`
- `storage_backend`
- `baidu_refresh_token`

注意：

- `BAIDU_APP_KEY`、`BAIDU_SECRET_KEY`、`BAIDU_SIGN_KEY` 仍然来自环境变量，不进库
- `GET /api/settings` 也不会返回 refresh token 明文

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

当前状态：

- `queued`
- `running`
- `completed`
- `failed`

当前进度推进大致会经过：

- 探测前后
- 分片完成后
- manifest 完成后
- 远端上传完成后
- 任务完成

## 启动时 schema bootstrap

当前 `initialize_database()` 负责：

1. 创建表
2. 为旧数据库补齐必要列

当前补齐逻辑已经覆盖：

- `videos.source_path`

## 当前未做的数据库能力

还没有实现：

- 版本化 migration
- 更细索引设计
- 远端对象同步状态字段
- 导入恢复断点字段
- 分片缓存表

这些等真实在线验收、异步导入和同步链路继续展开后再补更合适。
