# 学业ChatBI 演示版

基于开发部署文档实现的对话式成绩分析 MVP。当前版本使用代码内模拟数据，本地运行；线上通过 Vercel 同时部署 Vue 前端和 FastAPI Python Function。

## 目录

- `backend/`：FastAPI 后端
- `frontend/`：Vue3 前端
- `api/`：Vercel Python Function 入口
- `data/knowledge/`：知识库切片与评测用例

## 本地启动

### 后端

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY；不填也可用 mock 模式跑通流程
# DeepSeek 当前可用模型：deepseek-v4-pro / deepseek-v4-flash
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

## Vercel 部署

1. 在 Vercel 导入 GitHub 仓库。
2. 设置环境变量：
   - `DEEPSEEK_API_KEY`
   - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
   - `DEEPSEEK_MODEL=deepseek-v4-pro`
   - `DEEPSEEK_REASONER_MODEL=deepseek-v4-flash`
   - `USE_IN_MEMORY_DB=true`
3. 部署完成后，线上会使用内存虚拟数据，不需要 MySQL/SQLite。

## 演示账号

- 学生：`20230001` / `student123`
- 班长：`monitor01` / `monitor123`
- 辅导员：`counselor01` / `counselor123`

## 常用提问

- 我高数多少分
- 我们班挂科率是多少
- 年级各科平均分
- 各班平均分对比
- 高数分数段分布

侧边栏可直接运行整体成绩分布、挂科风险预警、班级横向对比、单科深度分析、纵向趋势对比、群体差异分析和归因分析。

## 说明

- 本地开发默认使用 SQLite；设置 `USE_IN_MEMORY_DB=true` 时使用内存虚拟数据，适配 Vercel。
- 配置 `DEEPSEEK_API_KEY` 后使用真实模型，默认 `deepseek-v4-pro`；归因分析默认 `deepseek-v4-flash`。
- 未配置 `DEEPSEEK_API_KEY` 时使用本地 mock 逻辑，可完整演示前端与权限链路。
- 首次启用真实 embedding 模型会下载一次，配置 `EMBEDDING_MODE=hash` 可完全离线。
- MySQL 迁移与容器化部署已预留，但本地 MVP 不依赖 Docker。
