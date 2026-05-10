# 本地导入与媒体探测

## 1. 当前导入切片的目标

当前导入已经不只是“把文件登记进数据库”，而是要完成一个更完整的导入闭环：

1. 验证本地主机路径
2. 记录导入任务状态
3. 写入视频元数据
4. 固定大小切片
5. AES-256-GCM 加密
6. 写入本地 staging 分片
7. 生成本地 manifest
8. 上传 manifest / 分片到当前 storage backend
9. 尽力抽取一张封面

## 2. 为什么当前仍保留同步导入

虽然最终形态更适合后台任务，但当前同步实现有两个优势：

1. 可以先稳定接口契约和状态流转
2. 自动化测试更容易覆盖整个导入闭环

因此当前 `POST /api/imports` 返回时，任务通常已经完成或失败。

## 3. 当前导入服务流程

`import_local_video()` 当前主要执行下面这些步骤：

1. 校验 `source_path` 存在且是文件
2. 如果传了 `folder_id`，校验目录存在
3. 创建 `queued` 导入任务
4. 标记为 `running`
5. 调用 `probe_video()` 获取媒体元数据
6. 写入 `videos`
7. 读取或生成本地主机内容密钥
8. 以固定大小遍历源文件
9. 对每个分片执行 AES-256-GCM 加密
10. 将密文写入本地 staging 目录
11. 将分片元数据写入 `video_segments`
12. 生成本地 `manifest.json`
13. 更新 `videos.manifest_path`
14. 通过当前 storage backend 上传 manifest 与所有加密分片
15. 尝试执行封面抽取
16. 标记任务为 `completed`
17. 任一关键步骤异常时标记为 `failed`

## 4. 媒体探测实现细节

当前使用外部命令：

```bash
ffprobe -v error -show_entries format=duration,format_name:stream=codec_type -of json <path>
```

当前关心的信息主要有：

- 是否存在视频流
- `duration`
- `format_name`

另外两项元数据来自本地文件系统 / 文件名推断：

- `size`
- `mime_type`

## 5. 固定大小切片

分片大小来自：

- `CSP_SEGMENT_SIZE_BYTES`

默认值：

- `4194304` 字节（`4 MiB`）

当前 `chunker` 只做**字节切片**，不做任何转码和封装改写。

## 6. 当前加密格式

每个分片使用：

- `AES-256-GCM`

当前会保存这些字段：

- `segment_index`
- `original_offset`
- `original_length`
- `ciphertext_size`
- `plaintext_sha256`
- `nonce_b64`
- `tag_b64`
- `cloud_path`
- `local_staging_path`

其中：

- `cloud_path` 是远端对象逻辑路径
- `local_staging_path` 是当前本地主机上的密文暂存文件路径

## 7. manifest 结构

当前本地 manifest 会写到：

- `data/segments/<video_id>/manifest.json`

manifest 里包含：

- 视频标题
- 源文件元数据
- `segment_size_bytes`
- `segment_count`
- 原始文件大小与 MIME
- 加密算法信息
- 每个分片的偏移、长度、checksum、remote path、nonce、tag

manifest 不包含：

- 明文内容密钥
- Session 凭据
- 登录密码材料

## 8. 当前上传行为

当前导入服务会把以下对象上传到配置的 storage backend：

- `manifest.json`
- `segments/*.cspseg`

### 当 backend=mock

会映射到本地目录：

- `data/mock-remote/apps/CloudStoragePlayer/videos/<video_id>/manifest.json`
- `data/mock-remote/apps/CloudStoragePlayer/videos/<video_id>/segments/*.cspseg`

### 当 backend=baidu

会上传到百度网盘应用目录，例如：

- `/apps/CloudStoragePlayer/videos/<video_id>/manifest.json`
- `/apps/CloudStoragePlayer/videos/<video_id>/segments/*.cspseg`

## 9. 封面抽取

当前封面抽取使用：

```bash
ffmpeg -y -ss 0 -i <path> -frames:v 1 <output>.jpg
```

策略：

- 从视频开头取第一帧
- 输出 JPG
- 成功时写到本地封面目录，并给 `videos.cover_path` 写入 `/covers/<video_id>.jpg`

失败策略：

- 封面失败不会让导入任务失败
- 但分片 / manifest 上传失败会导致导入任务失败

## 10. 当前失败语义

### 10.1 请求级失败

如果 `source_path` 本身不存在：

- 直接返回 `400`
- 说明请求无效

### 10.2 处理级失败

如果路径存在，但后续处理失败，例如：

- `ffprobe` 失败
- 不是有效视频
- 存储 backend 上传失败

则：

- 导入任务会进入 `failed`
- 接口仍返回任务记录

## 11. 与后续真实百度接入的关系

当前这套导入流程已经把最关键的边界固定住了：

- 本地路径导入入口
- 任务状态模型
- 分片元数据结构
- remote path 约定
- manifest 结构
- storage backend 抽象

当前已经有百度 backend 的最小实现，下一步更大的工作会转向：

- 在线验收
- 错误重试
- 远端同步
- 异步导入任务化

## 12. 关于 `tmp/` 测试视频

如果项目里已经放了测试视频，例如：

- `tmp/rieri.mp4`

那么可以直接把服务器看到的**绝对路径**传给导入接口，例如：

```json
{
  "source_path": "/root/cloud-storage-player/tmp/rieri.mp4",
  "title": "rieri sample"
}
```

自动化测试本身不依赖这个文件；测试会动态生成一个很小的 MP4 样例，以避免对外部文件产生硬依赖。
