# 测试与样例数据

## 1. 当前自动化测试覆盖

后端自动化测试当前覆盖：

- 页面登录流与 JSON 认证流
- Session 鉴权
- 目录接口
- 视频详情接口
- 设置 API
- 百度 OAuth 服务与授权接口
- 存储 backend 选择与基础行为
- 导入接口鉴权与错误分支
- 导入成功后的任务状态
- `ffprobe` 集成
- 封面抽取成功 / 失败分支
- 固定大小切片
- AES-GCM round trip
- `video_segments` 元数据落库
- mock 存储 backend 上传 / 下载
- Baidu storage backend 的上传 / 下载核心代码路径（fake API 测试）
- 远端元信息加密（远端名字混淆 + 远端 manifest 加解密）
- 远端 manifest 扫描 / catalog sync
- 播放流整文件返回
- Range / suffix range / `416`
- 源文件删除后的本地 staging 回放
- 源文件 + 本地 staging 删除后的远端回放
- 本地 / 远端 / 源文件都缺失时的 `404`

## 2. 当前推荐的验证命令

### 后端

```bash
uv run pytest
```

### 前端

```bash
cd frontend
npm run build
```

## 3. 样例视频策略

自动化测试不直接依赖仓库外部样例视频，而是通过 `ffmpeg` 运行时生成一个极小 MP4 文件。

原因：

1. 环境更稳定
2. 不依赖某个固定机器上的文件路径
3. 更适合后续持续集成

测试中使用的命令类似：

```bash
ffmpeg -y -f lavfi -i color=c=black:s=160x90:d=1 -c:v libx264 -pix_fmt yuv420p demo.mp4
```

## 4. 手工样例数据

如果你已经在项目内放了测试视频，例如：

- `tmp/rieri.mp4`

可以在服务启动后手工验证完整链路：

1. 登录系统
2. 调用 `POST /api/imports`
3. 查看 `GET /api/imports`
4. 查看 `GET /api/videos`
5. 打开 `GET /api/videos/{id}`
6. 使用前端或浏览器直接访问 `/api/videos/{id}/stream`

建议请求体示例：

```json
{
  "source_path": "/root/cloud-storage-player/tmp/rieri.mp4",
  "title": "tmp sample"
}
```

## 5. 当前手工验证建议

为了验证三层回退链路，可以按这个顺序手工测试：

### 场景 A：正常播放

- 导入完成后直接播放
- 此时通常命中本地 staging

### 场景 B：删除源文件后播放

- 删除原始 MP4
- 再次播放
- 应仍然可以命中本地加密分片

### 场景 C：删除源文件和本地 staging 后播放

- 删除原始 MP4
- 删除 `data/segments/<video_id>/`
- 再次播放
- 应从当前 storage backend 回退成功
  - mock：`data/mock-remote/apps/CloudStoragePlayer/<opaque_video_dir>/...`
  - baidu：百度网盘远端对象

### 场景 D：全部删除后播放

- 如果当前用 mock backend，再删除实际对应的远端混淆目录
  - 最简单的方法是先查看数据库里的 `videos.manifest_path`
  - 再删除 `data/mock-remote` 下该 manifest 所在目录
- 再次播放
- 应返回 `404`

## 6. 当前测试边界

虽然现在已经覆盖到百度 backend 的核心代码路径，但还**没有**覆盖：

- 真实百度账号在线上传 / 下载的自动化验收
- 前端单元测试
- E2E 浏览器播放测试
- 导入断点续传 / 恢复
