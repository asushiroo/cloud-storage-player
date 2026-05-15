# Cloud Storage Player

这是一个运行在 Windows 主机上的局域网视频服务：主机负责导入本地视频、按固定大小切片、AES-256-GCM 加密、写入本地元数据，并把加密分片与 manifest 上传到配置的存储后端；浏览器侧通过普通 `video` 标签访问后端 Range 流。

当前仓库采用**前后端分离**：

- 后端：FastAPI + SQLite + 服务层 / 仓储层 / 存储抽象
- 前端：`frontend/` 下的 React + TypeScript + Vite
- `third/`：参考代码，不参与当前运行时

## 2026-05 Cache Path Update
- Added configurable cache root path in settings API and settings page (`segment_cache_root_path`).
- New local segment writes now store `video_segments.local_staging_path` as cache-root-relative suffix only (example: `77/segments/000000.cspseg`).
- Existing local database values were migrated from absolute paths to suffix-only values after creating a DB backup.

## 2026-05-13 Playback Fix
- Playback now keeps the video element source intact across React StrictMode remounts and uses credentialed media requests.

## 2026-05-14 Playback And Like Fix
- Playback no longer stops silently when a later encrypted segment is missing remotely; if the original source file still exists, the backend now falls back to the corresponding source byte range and keeps streaming.
- Watch heartbeat analytics no longer write back stale `like_count`, so cancel-like operations are not overwritten by concurrent playback progress updates.

## 2026-05-14 Management And Player Follow-Up
- Cache list reads on `/api/cache/videos` now stay on `video_cache_entries` and no longer lazily rescan segment files during "查看缓存".
- Folder import is restored through `/api/imports/folders`, and the management page again supports switching between single-file import and folder batch import.
- The player local-cache visualization now uses a native-buffer-like bottom track that only appears while controls are active, and cached ranges stay stable during like/watch updates.

## 2026-05-15 Playback Freeze Fix
- API routes that still execute synchronous DB / filesystem / storage work are now declared as sync handlers, so FastAPI runs them in its worker threadpool instead of pinning the main event loop.
- Added a regression test that holds a stream segment download open and verifies `/api/videos` still responds during that blocked stream request.

## 2026-05-15 Dev Startup Port Fallback
- `npm run csp` now runs through `scripts/csp-dev.mjs`, which probes `CSP_PORT` (default `8000`) and automatically falls back to the next available port when occupied.
- Vite proxy now reads `CSP_PORT` so `/api` and `/covers` stay aligned with the backend port selected at startup.
- For direct `npm run backend`, you can still set `CSP_PORT` manually when a fixed port is required.

## 当前已实现

- 问题修复（2026-05 Problem.md）
  - 修复仅远端分片、无本地缓存时的播放起播路径：浏览器首个流请求现在可直接等待并读取远端分片返回，不再因本地缓存缺失而无法播放
  - 播放页交互改为内联 SVG 的点赞 / 取消点赞 / 跳高光操作区：点赞数仅在操作时以上浮数字动画反馈，跳高光按钮简化为记录分钟点位
  - 视频详情页移除重复点赞按钮，点赞交互统一收敛到播放页
  - 修复 Windows/GBK 环境下 `ffprobe`/`ffmpeg` 子进程输出解码导致的 `UnicodeDecodeError`：改为字节读取 + UTF-8/GB18030 回退解码
  - 导入封面抽帧改为按视频 `1/3` 时长位置生成，保持 `AVIF` + 本地加密存储
  - 新增批量重建封面 CLI：`cloud-storage-player-rebuild-posters`（对有源文件的视频按 1/3 帧重建 poster）
  - 导入任务列表响应移除 `source_path` 字段，任务栏不再展示源路径
  - 推荐页 3D 轮播标题改为独立固定左下角叠层，避免动画阶段标题跳位
  - 推荐页 3D 轮播标题改为随卡片一起切换与动画，消除图片旋转时文字不动、动画结束后文字跳帧问题
  - 推荐页次推荐位从 12 宫格改为 2 行 3 列（桌面 3 列，移动端 2 列）
  - 设置页输入框改为始终显示当前值（包含默认值），并在输入框悬停/聚焦时显示就地提示文本
  - 兼容历史 `/covers/*` artwork 路径：前后端统一归一化到 `/api/artwork/*`，避免旧数据详情页/列表页 404
  - 上传分片新增远端完整性保护：`mock` 后端下按远端文件尺寸校验，尺寸不一致会强制重传；manifest 始终重传避免元数据滞后
  - 导入完成后增加缓存上限淘汰：优先清理旧缓存，且保护当前新上传视频不被优先淘汰
  - 修复“退出播放页后仍持续请求百度网盘下载分片”的带宽浪费问题：播放预取改为首片优先响应后再按 5 片一批滚动预取；每批完成才会进入下一批，播放会话释放后立即停止后续预取
  - 修复历史 poster `.jpg` 路径导致前端无封面：API 对 `/covers/*-poster.jpg` 自动归一到 `/api/artwork/*-poster.avif`，`/api/artwork/*.jpg` 在缺失时可回退读取同名 `.avif` 加密封面
  - 管理页“查看缓存”改为纯数据库读取 `video_cache_entries`，不再在列表读取路径上回扫本地分片目录
  - 恢复管理页“导入文件夹”模式，并新增 `/api/imports/folders` 批量创建导入任务
  - 播放页本地缓存可视化改为贴近原生缓冲条的底部细条，且显隐时机跟随原生控件活跃状态
- UV 管理 Python 项目与依赖
- FastAPI 应用入口与 SQLite bootstrap
- 基于 Cookie Session 的单密码认证
- `/api/auth/*`、目录、视频详情、设置、导入接口
- 本地主机路径导入
- `ffprobe` 媒体探测
- 固定大小切片与 AES-256-GCM 加密
- `video_segments` 元数据落库
- 本地 manifest 生成
- 存储后端抽象
  - `mock`：本地目录模拟远端对象存储
  - `baidu`：基于百度网盘官方 open platform 的最小可用 backend
- 百度 OAuth 授权码换取 refresh token，并缓存 access token
- 导入时把 manifest / 加密分片上传到当前配置的存储后端
- 后台异步导入任务（API 入队，后台 worker 执行）
- 视频自定义标签
  - 导入时可填写多个标签
  - 视频详情页改为多标签小格子编辑
  - 支持添加 / 删除 / 双击编辑并自动保存
  - 标签持久化到本地数据库
  - 标签写入远端加密 manifest，sync 后可恢复
- 媒体库标签/关键词过滤
  - 支持按标题、源路径、标签关键词搜索
  - 支持按单个标签快速过滤
- 远端 manifest 扫描 / catalog sync
  - sync 兼容百度对不存在 legacy `/videos` 目录返回错误的情况
- 远端元信息加密
  - 远端视频目录名改为基于内容密钥的稳定混淆名
  - 远端分片文件名改为基于内容密钥的稳定混淆名
  - 远端 manifest 改为 AES-256-GCM 加密后的二进制 payload
  - sync 兼容历史明文 manifest 与新加密 manifest
- 百度 OpenAPI / PCS 的基础重试与退避
- 播放流优先读取本地加密分片，其次回退到远端对象，最后回退到源文件
  - 远端回退播放命中未缓存分片时，会直接使用内存中的远端分片完成当前响应，不再等待先写入本地缓存后再返回
  - 当前播放响应返回后会后台异步落盘远端分片缓存，避免磁盘写入阻塞首包与 seek
  - 远端回放会优先同步拉取当前所需首片，再后台按 5 片一批滚动并发预取（每批完成后才会进入下一批）；退出播放页/连接释放后会立即停止后续预取
  - 遇到百度远端分片 404 时会记录 warning 并中止当前流，避免 traceback 冒到服务端日志
- `ffmpeg` 封面抽取、AVIF poster 转码与加密 artwork 读取接口
- 真实百度链路 smoke CLI（上传 / 远端 sync / 远端回放校验）
- 已完成一次真实百度链路在线验收（`tmp/rieri.mp4` 上传 / sync / 远端回放通过）
- 前端已切换到 `frontend/` 中的新实现
  - 首页 `/` 现在重定向到独立推荐页 `/recommend`
  - 推荐页顶部保留 3D Banner，最近观看改为单行标题列表，次推荐位限制为 12 个视频
  - 媒体库独立到 `/library`，仅保留搜索、一级 / 二级标签筛选和 poster 墙
  - 媒体库卡片保持原来的 cover + 元信息布局，修复卡片收缩时封面溢出问题
  - 搜索与标签过滤在独立媒体库页完成；管理页专注导入、同步与任务管理
  - 登录页走 `/api/auth/login`
  - 推荐页走 `/api/videos/recommendations`
  - 媒体库页走 `/api/videos`
  - 管理页走 `/api/videos`、`/api/imports` 与缓存相关接口，不再依赖文件夹流
  - 视频详情页走 `/api/videos/{id}`、`PATCH /api/videos/{id}/tags`、`POST /api/videos/{id}/artwork`、`DELETE /api/videos/{id}`
  - 设置页走 `/api/settings`、`/api/settings/baidu/oauth`
  - 播放页直接使用后端 `/api/videos/{id}/stream`
- 导入 / 删除统一任务栏
  - 导入任务显示任务名而不是纯路径
  - 导入 / 缓存任务支持单条取消、全部取消；删除任务不可取消
  - 删除任务进度按阶段推进，不再从 10 直接跳到 100
- 本地缓存管理
  - 管理页默认显示本地缓存总大小
  - 可展开 4 列缓存封面网格，支持单视频清理与一键清理全部缓存
  - 视频详情页支持手动创建“缓存到本地”后台任务
- 后台任务网络速度展示
  - 导入上传任务与手动缓存下载任务会累计统计远端传输字节与基于真实墙钟时长的平均有效网速
  - 并发传输的开始/结束时间戳在 worker 线程内采集，避免主线程串行回收结果时把 5 并发任务统计得比真实吞吐更慢
  - 管理页任务栏展示当前任务网速与已传输大小
- 百度网盘远端传输提速与恢复
  - 导入上传默认并发 5 路
  - 手动“缓存到本地”任务默认并发 5 路
  - 设置页已支持分别持久化调整上传并发和下载并发，下载并发会影响手动缓存与播放预取，上传并发会影响导入上传
  - 上传遇到 `errno=9013` / `hit frequence control` 时不会直接失败，而是按小时轮询后继续
- 前端登录态体验优化
  - 浏览器会缓存最近一次 session 结果
  - 缓存 TTL 为 10 分钟；10 分钟内刷新/再次进入会先按上次结果放行
  - 首次访问或超过 TTL 后才重新发起 session 检查，避免频繁阻塞首屏
- 已完成任务与失败/取消任务分开清理
  - 删除视频改为后台删除任务，并出现在同一个任务栏
  - 删除远端对象后会继续尝试清理对应空视频目录
- 视频 artwork 管理
  - 首页、详情页、媒体库统一优先使用横版 poster
  - 导入时默认只生成固定横版 poster（1280×720），不再额外生成竖版 cover
  - poster 导入与手动替换统一转成 `AVIF`
  - poster 本地文件改为轻量加密保存，通过 `/api/artwork/{name}` 解密回传给前端
  - 播放页可捕获当前帧，只需调整一次横版 poster 的缩放与截取位置后再保存
  - 应用成功后会自动收起当前截图预览
- 播放页交互增强
  - 保留浏览器 / iPad 原生视频控件，不再额外叠加自定义播放 / 快进 / 后退图标
  - 手动替换 cover / poster 后会立即刷新前端媒体库中的 artwork
  - 推荐分 / 兴趣分 / 热门分继续保留在后端统计，但前端不再直接展示
- 首页推荐位
  - 顶部 Banner 改为 3 张横版 poster 的 3D 轮转展示
  - 标题文字直接叠加在 poster 图片上
  - Banner 高度不再用固定容器裁切，改为随 3D 轮播比例自然撑开
- 顶部导航
  - 搜索栏移动到顶部导航区
  - 导航页签改为扁平文本风格，当前项仅做文字高亮与下划线提示
- 首页筛选
  - 内容区宽度调整为 90vw，左右留白约 5%
  - 轮播图与下方内容区保持等宽，目录 / 标签栏放在轮播图下方，并通过短横线分区
  - 一级标签默认显示，只有选中一级标签后才显示二级标签
  - 视频卡片标签分为两行展示，并限制单行不换行溢出
  - 二级标签前缀继续只作为内部存储细节处理，前端展示与编辑不再暴露
- 管理页导入
  - 改为先选择“导入视频”或“导入文件夹”，再显示对应输入框与提交按钮
- 播放页 artwork 编辑
  - poster 预览区改成左右两栏：左侧缩小预览，右侧裁切调节
- 视频详情页
  - 移除头部重复标签显示与源文件 meta，仅保留下方标签编辑区
  - 去掉 `Video #id` 文案与“返回媒体库”按钮
  - 封面可直接点击进入播放页，并修复手机端详情封面导致横向滚动的问题
  - “缓存到本地”按钮改为“缓存”，仅在视频未完整缓存时显示；部分缓存时会跳过已存在分片继续补齐
  - 删除按钮文案统一收敛为“删除”
- 首页推荐位与媒体库布局微调
  - 3D Banner 调整为更明显的透视旋转效果，并放宽到完整内容宽度显示
  - 桌面端媒体库卡片保持 4 列展示，不再在中等宽度提前降到 3 列
  - Banner 改为独立于媒体库内容区的顶部容器，Banner 与下方内容都直接按页面级 `90vw` 对齐，不再叠加嵌套百分比宽度
  - Banner 调整为中间主卡 + 左右透视侧卡的轮播样式，补上实际过渡动画
  - Banner 交互改为点击中间主卡进入视频详情，点击左右侧卡或左右箭头切换，不再支持按住拖动切换
  - 首页 Banner 候选已从纯随机切到优先读取后端推荐位，个性化候选不足时回退热门内容
  - 推荐页新增“最近观看”单行标题模块，直接展示上次播放位置较新的未看完视频
  - Banner 外层高度改为跟随主卡宽度和 16:9 比例自动撑开，避免宽屏继续放大时被固定高度卡住
  - Banner 动画终点与静态卡位统一，并修正中间卡切到侧卡时的 `transform-origin`，消除切换结束时额外跳帧和卡顿
  - Banner 切换时复用同一批卡片节点，避免动画落点正确后仍因节点重建产生视觉卡顿
  - Banner 支持每 10 秒自动轮转一次
  - 推荐页“最近观看”继续沿用 `continue_watching` 候选，但进入页面会强制刷新，前端最多展示 5 条
  - 媒体库页调整为“全部视频”视图：默认不选标签时展示全部视频，仅保留一级 / 二级标签筛选，视频网格按 12 张一批继续展开
- 播放统计与推荐基础
  - 新增单机单用户播放会话统计：有效播放次数、总会话数、总观看时长、最近播放位置、跳出率、重看倾向
  - 后端会按一二级标签累计偏好分，并回写推荐分、继续观看分、缓存优先级
  - 播放页新增观看心跳上报与“跳到高潮”按钮；高光区间基于轻量 heatmap 计算
  - 媒体库 poster 墙改为每次先展示 12 张，并随滚动继续展开后续视频
- 左上角站点标题已替换为 `frontend/asserts/` 中的 logo
- `uv run pytest` 自动化测试

## 当前仍未完成

- 新环境首次接入百度时，仍需要管理员手工完成一次 OAuth 授权码流程
- 导入断点续传、LRU 分片缓存
- 更完整的百度错误分类与更细粒度的长时退避策略
- 远端封面同步与更完整的 catalog 元数据恢复
- 当前前端只保证 Web 主链路，移动端不是本阶段目标
- 目前还没有批量删除/批量清空媒体库，当前仍以单视频删除任务为主
- 任务取消目前是协作式取消：已排队任务会立刻取消，运行中任务会在阶段边界停止

## Python 版本

项目当前目标版本为 `Python 3.12`。

## 快速开始

### 后端

```bash
uv sync --dev
uv run cloud-storage-player
```

默认监听：

- Host: `0.0.0.0`
- Port: `8000`

### 前端开发

```bash
npm install
npm run dev
```

说明：在项目根目录执行一次 `npm install` 时，会自动继续安装 `frontend/` 下的依赖，不需要再单独进入 `frontend/` 执行安装。

当前页面结构：

- `/`：重定向到 `/recommend`
- `/recommend`：推荐页，包含 3D Banner、最近观看单行列表、12 宫格次推荐位
- `/library`：独立媒体库，包含搜索、一级 / 二级标签筛选和 poster 分批展开
- `/manage`：单文件导入、文件夹批量导入、同步与任务管理
- `/settings`：运行设置与百度授权

如果后端地址不是默认值，可创建 `.env.local`：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 环境变量

统一使用 `CSP_` 前缀，可放在 `.env` 中。

### 基础配置

- `CSP_APP_NAME`
- `CSP_HOST`
- `CSP_PORT`
- `CSP_SESSION_SECRET`
- `CSP_PASSWORD`
- `CSP_PASSWORD_HASH`
- `CSP_DATABASE_PATH`

### 媒体处理与本地文件

- `CSP_FFPROBE_BINARY`
- `CSP_FFMPEG_BINARY`
- `CSP_COVERS_PATH`
- `CSP_CONTENT_KEY_PATH`
- `CSP_SEGMENT_STAGING_PATH`
- `CSP_SEGMENT_SIZE_BYTES`

### 存储后端

- `CSP_STORAGE_BACKEND`
  - 当前默认：`mock`
  - 可选：`mock` / `baidu`
- `CSP_REMOTE_TRANSFER_CONCURRENCY`
  - 当前默认：`5`
  - 兼容旧配置的总并发默认值；若未单独设置上传/下载并发，会作为两者的后备值
- `CSP_UPLOAD_TRANSFER_CONCURRENCY`
  - 可选，允许范围：`1` 到 `32`
  - 未设置时回退到 `CSP_REMOTE_TRANSFER_CONCURRENCY`
- `CSP_DOWNLOAD_TRANSFER_CONCURRENCY`
  - 可选，允许范围：`1` 到 `32`
  - 未设置时回退到 `CSP_REMOTE_TRANSFER_CONCURRENCY`
- `CSP_BAIDU_UPLOAD_RESUME_POLL_INTERVAL_SECONDS`
  - 当前默认：`3600`
- `CSP_MOCK_STORAGE_PATH`
  - 当前默认：`data/mock-remote`
- `CSP_BAIDU_OAUTH_REDIRECT_URI`
  - 当前默认：`oob`
  - 用于百度 OAuth 授权码回调参数

### 前后端联调

- `CSP_CORS_ALLOWED_ORIGINS_RAW`
- `VITE_API_BASE_URL`

### 百度网盘开放平台凭据

这些值按项目约定来自**不带 `CSP_` 前缀**的环境变量：

- `BAIDU_APP_KEY`
- `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY`

说明：

- 当前上传 / 下载链路实际使用 `BAIDU_APP_KEY` 与 `BAIDU_SECRET_KEY`
- `BAIDU_SIGN_KEY` 先保留，后续更深的开放能力接入时可能会用到

## 当前接口

认证：

- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`

目录与播放：

- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `PATCH /api/videos/{video_id}/tags`
- `POST /api/videos/{video_id}/like`
  - 可通过请求体 `{"delta": 1}` / `{"delta": -1}` 或查询参数 `?delta=1` / `?delta=-1` 指定增减；缺省仍等价于点赞 `+1`
- `POST /api/videos/{video_id}/artwork`
- `DELETE /api/videos/{video_id}`（创建删除任务）
- `GET /api/videos/{video_id}/stream`

导入：

- `POST /api/imports`
- `POST /api/imports/folders`
- `POST /api/imports/{job_id}/cancel`
- `POST /api/imports/cancel-all`
- `DELETE /api/imports?status_group=completed|failed`
- `GET /api/imports`

缓存：

- `GET /api/cache`
- `GET /api/cache/videos`
- `DELETE /api/cache`
- `DELETE /api/cache/videos/{video_id}`
- `POST /api/videos/{video_id}/cache`
- `GET /api/imports/{job_id}`

同步：

- `POST /api/videos/sync`

设置：

- `GET /api/settings`
- `POST /api/settings`
- `POST /api/settings/baidu/oauth`

## 百度授权最小流程

1. 在后端环境里配置 `BAIDU_APP_KEY`、`BAIDU_SECRET_KEY`
2. 打开设置页或调用 `GET /api/settings`
3. 取返回的 `baidu_authorize_url`
4. 在浏览器打开授权页，完成授权
5. 把返回的 `code` 提交到 `POST /api/settings/baidu/oauth`
6. 再把 `storage_backend` 切到 `baidu`

## 测试与验证

后端测试：

```bash
uv run pytest
```

如果当前机器没有把 `ffmpeg` / `ffprobe` 放进 `PATH`，依赖真实视频生成与探测的集成测试会失败；本轮新增的远端传输并发 / 频控恢复 / 持续预取测试不依赖这些外部二进制。

前端构建：

```bash
npm run build
```

真实百度 smoke：

```bash
uv run cloud-storage-player-baidu-smoke
```

如果还没有 refresh token，先按脚本打印的授权链接拿到 `code`，再执行：

```bash
uv run cloud-storage-player-baidu-smoke --oauth-code "你的百度授权码"
```

如果你想直接用 `tmp/rieri.mp4` 跑真实百度链路：

```bash
uv run cloud-storage-player-baidu-smoke --source-path tmp/rieri.mp4
```

如果你在项目 `tmp/` 目录放了测试视频，例如 `tmp/rieri.mp4`，可以在服务启动后通过 `POST /api/imports` 手工导入验证。

## 技术文档

- [docs/README.md](docs/README.md)
- [docs/technical-overview.md](docs/technical-overview.md)
- [docs/storage-backend-and-remote-fallback.md](docs/storage-backend-and-remote-fallback.md)
- [docs/baidu-openapi-integration.md](docs/baidu-openapi-integration.md)

## 2026-05-14 UI Follow-Up
- Removed the player cache visualization overlay from the playback page to avoid misleading range rendering.
- Library listing now defaults to newest imported videos first (by `created_at` descending, then `id` descending).
- Recommendation secondary grid now switches from 3 columns to 2 columns earlier on medium-width viewports to prevent overflow.
