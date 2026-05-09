# 存储后端与远端回退

## 1. 目标

这一层的目标不是“先把百度 SDK 接上”，而是先把**服务层与远端对象存储解耦**。

因此当前实现先引入统一存储契约，再用本地目录模拟远端对象。

## 2. 当前代码结构

- `src/app/storage/base.py`
  - 定义存储接口
- `src/app/storage/mock.py`
  - 本地目录版 mock backend
- `src/app/storage/factory.py`
  - 根据配置选择 backend
- `src/app/storage/baidu.py`
  - 真实百度实现的占位文件

## 3. 存储契约

当前抽象保留了最小必要能力：

- `upload_file(local_path, remote_path)`
- `upload_bytes(payload, remote_path)`
- `download_bytes(remote_path)`
- `exists(remote_path)`

这足够覆盖当前阶段：

- 导入上传 manifest / 分片
- 播放时按 remote path 下载加密分片
- 回退前先判断远端对象是否存在

## 4. mock backend 的路径映射

当前 mock backend 会把远端路径映射到本地目录。

例如：

- 远端：`/CloudStoragePlayer/videos/3/manifest.json`
- 映射后：`<mock_root>/CloudStoragePlayer/videos/3/manifest.json`

分片路径同理：

- 远端：`/CloudStoragePlayer/videos/3/segments/000005.cspseg`
- 映射后：`<mock_root>/CloudStoragePlayer/videos/3/segments/000005.cspseg`

这样做的好处是：

1. manifest / segment 的 remote path 结构已经提前稳定
2. 自动化测试不需要真实云账号
3. 后续切换到百度实现时，数据库里的 `cloud_path` 结构不需要重设计

## 5. 导入时的上传时机

当前导入服务流程里，上传发生在：

1. 视频元数据落库之后
2. 本地 staging 分片写完之后
3. 本地 manifest 生成之后
4. 封面抽取之前

也就是顺序上大致是：

- 先保证本地加密分片存在
- 再把这些分片与 manifest 上传到存储 backend
- 再做非关键的封面抽取

这能保证：

- 播放核心数据先准备好
- 封面失败不会影响远端分片上传

## 6. 回放时的读取优先级

当前 `StreamService` 的逻辑是：

### 第 1 层：本地 staging

如果请求所需的加密分片仍在本地 staging 目录中，直接读取本地文件。

### 第 2 层：mock 远端对象

如果本地 staging 缺失，但数据库中有 `cloud_path`，并且 mock backend 中该对象存在，则下载远端加密分片。

### 第 3 层：源文件回退

如果无法使用加密分片链路，才回退到最初的源文件路径。

## 7. 为什么回退顺序是这样

### 先本地 staging

- 速度最快
- 不需要额外 I/O 映射
- 适合刚导入后的立即播放

### 再 mock 远端对象

- 更接近未来真实部署形态
- 可以验证“源文件删除后仍能播放”的能力

### 最后源文件回退

- 保持当前阶段可调试性
- 防止远端链路尚未稳定时播放器彻底不可用

## 8. 当前限制

- mock backend 不是最终生产实现
- 还没有远端目录扫描 / catalog sync
- 还没有分片缓存淘汰策略
- 还没有重试、断点续传、多段并发下载
- `baidu` backend 仍是占位

## 9. 下一阶段最自然的演进方向

1. 用真实百度 API 替换 `mock` backend
2. 增加远端 manifest 扫描与目录同步
3. 加入分片缓存与 LRU 回收
4. 把导入任务升级为后台异步任务
