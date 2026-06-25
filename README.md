# 舆情智析平台

面向实践竞赛的舆情分析闭环：任务配置、Excel/媒体导入、Ollama持续研判、人工修正、增量应对策略、态势大屏和PDF归档报告。

## 快速启动（SQLite）

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python backend/scripts/seed_demo.py
.venv/bin/python backend/scripts/generate_test_data.py
.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

另开一个终端：

```bash
cd frontend
pnpm install
pnpm dev
```

打开 <http://127.0.0.1:5173>。接口文档位于 <http://127.0.0.1:8000/docs>。

依赖安装完成后，也可以在项目根目录使用一个命令同时启动前后端：

```bash
./start.sh
```

按 `Ctrl+C` 会同时关闭两个服务。Ollama需要保持独立运行。

### 临时分享给外网同学

macOS 首次安装 Cloudflare Tunnel 客户端（不依赖 Homebrew）：

```bash
./install-cloudflared.sh
```

之后在项目根目录执行：

```bash
./share.sh
```

终端会输出一个 `https://xxxx.trycloudflare.com` 临时地址，把它发给同学即可。保持终端和电脑运行，按 `Ctrl+C` 会同时关闭隧道和本地前后端。临时地址会变化，仅用于短期测试。

## 使用 MySQL

先创建数据库：

```sql
CREATE DATABASE opinion_sentinel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

复制 `.env.example` 为 `.env`，修改：

```env
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/opinion_sentinel?charset=utf8mb4
OLLAMA_MODEL=你的本地模型名称
```

当前版本会自动建表。比赛版本只启动一个 Uvicorn worker，后台分析循环通过数据库状态续跑。

## Excel导入

从管理端下载标准模板。必填列为“平台”和“正文”。点赞量、评论量、转发量分别填写，系统自动计算互动总量；阅读/播放量作为曝光指标单独统计。看不到的指标填0。需要图片或视频时，同时上传媒体ZIP，Excel中的“图片文件”“视频文件”填写ZIP内文件名。

## 验证

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
cd frontend && pnpm run build
```

## Docker 一键部署到服务器

推荐使用 Ubuntu 24.04 LTS（x86_64）。把整个项目上传或克隆到服务器后执行：

```bash
cd opinion-sentinel
chmod +x deploy.sh
./deploy.sh
```

脚本会自动完成以下工作：

- Ubuntu/Debian 未安装 Docker 时自动安装 Docker Engine 与 Compose 插件；
- 自动生成 MySQL 随机密码和团队访问密码；
- 启动 Nginx、FastAPI、MySQL、Ollama；
- 首次拉取 `qwen2.5:3b` 模型；
- 持久化数据库、导入媒体和 Ollama 模型。

首次部署需要下载镜像和模型，耗时取决于服务器网络。部署完成后使用服务器公网 IP 访问。云服务器安全组只需放行：

- TCP 22：SSH，建议仅允许自己的 IP；
- TCP 80：网站访问；
- 后续配置 HTTPS 时再放行 TCP 443。

不要向公网开放 3306、8000、11434。项目当前没有正式用户体系，Docker 版本已在 Nginx 增加团队共享密码保护，账号密码保存在服务器项目目录的 `.env.deploy`。

常用维护命令：

```bash
# 查看运行状态
docker compose --env-file .env.deploy ps

# 查看实时日志
docker compose --env-file .env.deploy logs -f

# 更新代码后重新部署
./deploy.sh

# 停止服务，但保留数据库、媒体和模型
docker compose --env-file .env.deploy down

# 启动已有服务
docker compose --env-file .env.deploy up -d
```

需要切换为 7B 模型时，修改 `.env.deploy`：

```env
OLLAMA_MODEL=qwen2.5:7b
```

然后重新执行 `./deploy.sh`。不要执行 `docker compose down -v`，`-v` 会删除数据库、媒体和模型卷。
