# 百度网盘 OpenAPI 接入

## 1. 当前实现范围

当前仓库已经把百度网盘 open platform 接入到了一个**最小可用后端切片**，覆盖了：

1. 生成授权地址
2. 用授权码换取 refresh token
3. 用 refresh token 刷 access token
4. 导入时上传 manifest 与加密分片
5. 播放时按 remote path 查询文件、拿 dlink、下载远端密文
6. 远端 manifest 扫描 / sync
7. 基础重试与退避
8. 真实百度 smoke CLI 与手工在线验收

当前还没有做：

- 大文件多分片并发上传优化
- 更细的错误重试 / 限流退避
- 真实在线账号 CI

## 2. 当前使用到的官方接口

### OAuth

- `GET https://openapi.baidu.com/oauth/2.0/authorize`
- `GET https://openapi.baidu.com/oauth/2.0/token`

### 文件上传

- `POST https://pan.baidu.com/rest/2.0/xpan/file?method=precreate`
- `POST https://d.pcs.baidu.com/rest/2.0/pcs/superfile2?method=upload`
- `POST https://pan.baidu.com/rest/2.0/xpan/file?method=create`

### 文件查询与下载

- `GET https://pan.baidu.com/rest/2.0/xpan/file?method=list`
- `GET https://pan.baidu.com/rest/2.0/xpan/multimedia?method=filemetas`
- 使用 `filemetas` 返回的 `dlink` 下载实际文件内容

## 3. 为什么仍然保留 storage 抽象

即使已经接入了真实百度 backend，服务层仍然不应该直接依赖百度接口细节。

当前结构是：

- `storage/base.py`
- `storage/mock.py`
- `storage/baidu_api.py`
- `storage/baidu.py`
- `storage/factory.py`

这样导入服务和回放服务只依赖：

- `upload_file`
- `upload_bytes`
- `download_bytes`
- `exists`

未来如果百度接口策略变化，主要改动仍然应该收敛在 `storage/baidu*.py` 内。

## 4. OAuth 授权设计

## 4.1 当前目标

当前目标不是做一个完整网页回调登录系统，而是给管理员提供一条可操作的最小授权链路：

1. 后端生成授权链接
2. 管理员打开百度授权页
3. 管理员拿到 `code`
4. 管理员把 `code` 提交回后端
5. 后端保存 refresh token

## 4.2 当前配置项

### `CSP_BAIDU_OAUTH_REDIRECT_URI`

- 默认值：`oob`
- 用于 OAuth 授权码流程中的 `redirect_uri`

### `BAIDU_APP_KEY`
### `BAIDU_SECRET_KEY`

- 当前优先读取后端 `/admin` 页面保存的本地设置
- 如果本地设置为空，则回退读取环境变量
- 用于生成授权地址，以及授权码换 token / refresh token 刷新 access token

## 4.3 当前数据落点

refresh token 当前保存在本地 SQLite `settings` 表里，对应 key：

- `baidu_refresh_token`

注意：

- `GET /api/settings` 不会返回 refresh token 明文
- 只会返回 `baidu_has_refresh_token: true/false`

## 5. 为什么默认远端根路径是 `/apps/CloudStoragePlayer`

百度官方上传文档中的示例路径都位于：

- `/apps/appName/...`

因此当前默认 `baidu_root_path` 已切到：

- `/apps/CloudStoragePlayer`

这让当前默认值直接符合百度网盘开放平台的路径约束。

另外，当前 `BaiduStorageBackend` 还会做一层兼容：

- 如果数据库中的历史路径还是 `/CloudStoragePlayer/...`
- backend 会在内部标准化为 `/apps/CloudStoragePlayer/...`

这样可以减少从 mock 阶段切到真实百度阶段时的兼容成本。

## 6. 上传链路实现

## 6.1 当前上传粒度

当前不是把整个原始视频直接发到百度，而是：

1. 原始视频先在本地切成固定大小分片
2. 每个分片先在本地做 AES-256-GCM 加密
3. 每个**加密分片文件**作为一个独立远端对象上传
4. 本地 manifest 也会先转成“远端加密 manifest”，再作为一个独立远端对象上传

这意味着百度侧存储的是：

- `<opaque_manifest>.bin`
- `<opaque_segment>.bin`

而不是明文视频文件。

另外，当前远端元信息也被保护：

- 视频目录名不是明文 `video_id`
- 分片文件名不是明文序号
- manifest 内容不是明文 JSON

这样百度侧只能看到加密后的二进制对象和混淆后的名字。

## 6.2 当前百度上传步骤

对于一个待上传对象，当前 backend 会执行：

1. 计算对象整体 MD5
2. 计算前 256KB 的 `slice-md5`
3. 调用 `precreate`
4. 如果 `return_type == 2`，说明云端已存在相同对象，直接复用
5. 否则调用 `superfile2` 上传唯一分片
6. 再调用 `create` 完成对象提交

## 6.3 为什么当前只上传单个 part

虽然百度上传接口支持多分片，但当前系统里上传到百度的单个对象主要是：

- 一个加密分片文件
- 一个 manifest 文件

而“加密分片文件”本身已经是导入流程切出来的小对象，默认大小 4 MiB。

因此这一阶段没有再在百度上传层做二次复杂切片，避免把复杂度堆叠两次。

## 7. 下载链路实现

当前播放时，如果本地 staging 缺失而 storage backend 是 `baidu`，会走这条链路：

1. 根据分片 `cloud_path` 定位远端对象路径
2. 通过 `list` 查询父目录下条目
3. 根据条目拿到 `fs_id`
4. 调用 `filemetas` 并要求返回 `dlink`
5. 使用 `dlink` 下载远端密文对象
6. 在服务端解密并裁剪成浏览器需要的 Range 字节

## 7.1 为什么先 `list` 再 `filemetas`

因为 `filemetas` 的主输入是 `fsids`，而我们本地数据库保存的是逻辑 remote path。

所以当前实现使用：

- `list(parent_dir)`
- 按 `path` 精确匹配目标文件
- 再把 `fs_id` 传给 `filemetas`

这是当前阶段最直接、最清晰的实现路径。

## 7.2 下载时的 HTTP 细节

百度文档对 dlink 下载的说明里有几个关键点：

- `dlink` 有有效期
- 下载请求必须带 `User-Agent: pan.baidu.com`
- dlink 存在 `302` 跳转

因此当前 `BaiduOpenApi` 默认使用：

- `User-Agent: pan.baidu.com`
- 跟随重定向

## 8. 当前接口暴露给前端的状态

`GET /api/settings` 当前会返回：

- `storage_backend`
- `baidu_root_path`
- `cache_limit_bytes`
- `baidu_authorize_url`
- `baidu_has_refresh_token`

`POST /api/settings/baidu/oauth` 当前接收：

```json
{"code":"..."}
```

成功后会保存 refresh token，并返回最新设置快照。

## 9. 当前风险与限制

### 9.1 尚未接入真实账号 CI

虽然现在已经有真实百度 smoke CLI，并且做过一次手工在线验收，但当前仓库测试仍然主要依赖 fake API / mock backend，而不是拿真实百度账号做 CI。

### 9.2 重试与退避仍然偏基础

当前已经有基础重试与退避，但仍然缺少：

- 更细的错误分类
- 更长时间窗口的限流恢复策略
- 上传并发/吞吐调优
- 断点续传

## 10. 下一阶段建议

最自然的下一步是：

1. 增加导入断点续传
2. 增加更细的百度错误恢复策略
3. 增加上传并发优化
4. 增加真实账号 CI 或半自动验收流水线
