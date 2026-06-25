# 数据采集模块对接约定

采集模块扫描 `tasks` 表中 `status = 'running'` 的任务。

任务配置字段：

- `id`：任务ID，采集结果必须关联到此ID
- `name`：任务名称
- `keywords`：JSON关键词数组
- `platforms`：JSON平台数组
- `start_time`、`end_time`：可同时为空，也可以只填写一个
- `updated_at`：任务配置最后修改时间

采集结果写入 `source_items` 表。建议至少写入：

- `task_id`
- `platform`
- `external_id`：平台原始数据ID
- `title`
- `author`
- `publish_time`
- `content`
- `source_url`
- `like_count`：点赞量
- `comment_count`：评论量
- `share_count`：转发/分享量
- `view_count`：阅读/播放量
- `interaction_count`：互动总量，等于点赞量+评论量+转发量
- `dedupe_key`：建议计算 `SHA256(平台 + external_id)`
- `analysis_status`：新数据固定写入 `pending`
- `created_at`、`updated_at`

新数据入库后，如果任务的 `analysis_enabled = 1`，后台分析循环会自动发现并继续逐条研判。采集模块不要写入分析结果表，也不要修改 `current_analysis_id`。
