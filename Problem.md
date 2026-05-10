# Problem.md

经过我的体验现在出现以下问题

- 当前cover还是会超出div的限制导致错乱，同时随着影片的增加，一行影片太多了，给我限制最多4列
- 标签有点小，并且叉按钮有背景色很难看
- 捕获当前帧并应用后应该给预览取消掉而不是一直在页面上显示
- 给导出与任务页面中的搜索媒体库功能转到媒体库界面，搜索的结果就是海报墙展示的内容，默认是全部内容，点击标签之后就再海报墙显示标签包含的:w
- 同时在取消任务之后出现了一个bug
  Exception in thread cloud-storage-player-import-worker:
  Traceback (most recent call last):
  File "/home/asushiro/Projects/cloud-storage-player/src/app/services/import_worker.py", line 72, in \_run
  process_background_job(self.settings, job_id)
  File "/home/asushiro/Projects/cloud-storage-player/src/app/services/background_jobs.py", line 16, in process_background_job
  raise ImportValidationError(f"Import job does not exist: {job_id}")
  app.services.imports.ImportValidationError: Import job does not exist: 19

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
File "/usr/lib/python3.12/threading.py", line 1073, in \_bootstrap_inner
self.run()
File "/usr/lib/python3.12/threading.py", line 1010, in run
self.\_target(\*self.\_args, \*\*self.\_kwargs)
File "/home/asushiro/Projects/cloud-storage-player/src/app/services/import_worker.py", line 74, in \_run
mark_import_job_failed(self.settings, job_id, error_message=str(exc))
File "/home/asushiro/Projects/cloud-storage-player/src/app/repositories/import_jobs.py", line 182, in mark_import_job_failed
return \_update_import_job(
^^^^^^^^^^^^^^^^^^^
File "/home/asushiro/Projects/cloud-storage-player/src/app/repositories/import_jobs.py", line 340, in \_update_import_job
return \_row_to_import_job(row)
^^^^^^^^^^^^^^^^^^^^^^^
File "/home/asushiro/Projects/cloud-storage-player/src/app/repositories/import_jobs.py", line 373, in \_row_to_import_job
id=row["id"],

```^^^^^^
TypeError: 'NoneType' object is not subscriptable

- 清除已完成任务和清理失败任务分开，不然全清了我怎么重做失败任务呢
- 取消任务应该具有原子性，取消了也要讲远程baidu上的内容删掉避免占用空间也没法处理，因为远程是加密信息也无法复查
- scanner上的文字太多了，应该只有一个标题，并且较小的在右下角
```
