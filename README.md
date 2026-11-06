# 技术笔试作品集

本仓库用于集中保存个人完成的技术笔试题及其实现代码，涵盖前端开发、后端开发、Python 开发、爬虫开发等技术方向。

各笔试项目独立组织，提供题目要求、技术栈、实现说明和运行方式，便于招聘人员和技术面试官快速查看与验证。

## 项目目录

| 目录 | 题目类型 | 简介 | 仓库 |
|---|---|---|---|
| [Front-end/](Front-end/) | 前端开发笔试 | 基于 Figma 设计稿高精度还原「上传简历」页面（React + TypeScript + Vite） | — |
| [Back-end/](Back-end/) | 后端开发笔试 | Spring Boot 3.2 + Spring Security 6 会话认证 REST API（登录/登出/CSRF/极简 Web 页面） | [spring-security-auth-demo](https://github.com/SunGuistar/spring-security-auth-demo) |
| [Crawler/](Crawler/) | 爬虫开发笔试 | Playwright 与 DrissionPage 双框架并行爬取 MIT Admissions 博客（FastAPI + SSE 进度推送） | [mit-blog-crawler](https://github.com/SunGuistar/mit-blog-crawler) |
| [Python/StreamingAPIDemo/](Python/StreamingAPIDemo/) | Python 开发笔试 | FastAPI 实现 SSE 流式 API Demo（StreamingResponse + 异步生成器 + ReadableStream） | [streaming-api-demo](https://github.com/SunGuistar/streaming-api-demo) |

各目录均为独立 Git 仓库，可单独克隆运行；题目详情与实现说明见各目录内的 README.md。

## 运行方式

### Front-end：Figma 设计稿还原 —— 上传简历页面

```bash
cd Front-end/app
npm install
npm run dev
```

- 本地访问地址：http://localhost:5173
- 生产构建：`npm run build`（输出至 `Front-end/app/dist/`）
- 自动化测试：`npm run test:e2e`（自动启动 dev server，使用系统 Edge 无头浏览器完成多尺寸截图与交互验收，结果输出到 `Front-end/app/test/report.json`）

题目详情与实现说明见 [Front-end/README.md](Front-end/README.md)。

### Back-end：Spring Security 认证 REST API

Java 17 + Spring Boot 3.2.0 + Spring Security 6，Session 会话认证（无 JWT/数据库），内存用户 `test / 123456`（BCrypt 加密），并提供极简 Web 测试页面（登录 → 访问受保护接口 → 登出）。

```bash
cd Back-end
mvn spring-boot:run
```

- 本地访问地址：http://localhost:8080/ （Web 测试页）；REST API 基地址 `http://localhost:8080/api`
- 运行测试：`mvn test`（MockMvc + Spring Security Test，8 个集成场景全部通过）
- 首次运行如本机无 JDK 17 / Maven，可使用仓库内置工具链（见下文「运行环境」）
- API 一览：`POST /api/login`（JSON 登录，需 CSRF Token）、`GET /api/hello`（受保护）、`GET /api/csrf`、`POST /api/logout`；完整 curl / PowerShell 演示命令见 [Back-end/README.md](Back-end/README.md)

### Crawler：双框架博客爬虫（Playwright + DrissionPage）

Python + FastAPI。点击一次「开始采集」，Playwright 与 DrissionPage 两套爬虫**并行独立运行**，页面分别实时展示进度（SSE），分别保存 CSV 与断点，支持停止/重置/断点续爬，用于直观对比两框架表现。

```bash
cd Crawler
pip install -r requirements.txt
python -m playwright install chromium   # 无网络时可跳过，自动回退系统 Chrome
python -m backend.main
```

- 本地访问地址：http://127.0.0.1:8000/
- 采集结果：`Crawler/data/playwright_results.csv`、`Crawler/data/drissionpage_results.csv`（UTF-8 BOM，六字段）
- 数据质量校验：`python -m backend.validator`（报告输出到 `logs/validation_report.json`）
- 离线测试：`python -m unittest tests.test_parser`（9/9 通过，fixtures 快照不访问网络）
- 详见 [Crawler/README.md](Crawler/README.md)

### Python/StreamingAPIDemo：FastAPI 流式 API（SSE）

FastAPI + `StreamingResponse` + 异步生成器实现 SSE 流式推送；前端用 Fetch `ReadableStream` 逐块渲染，`AbortController` 实现 Stop 中断。

```bash
cd Python/StreamingAPIDemo/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- 本地访问地址：http://localhost:8000/ （Swagger 文档：`/docs`）
- 健康检查：`GET /api/health`；流式接口：`POST /api/stream`，body `{"prompt": "..."}`
- curl 验证：`curl -N -X POST http://localhost:8000/api/stream -H "Content-Type: application/json" -d "{\"prompt\":\"Introduce FastAPI\"}"`
- 详见 [Python/StreamingAPIDemo/README.md](Python/StreamingAPIDemo/README.md)

## 运行环境

- Node.js：v20（开发验证版本为 v20.18，其他 Node 18+ 版本应兼容）
- 包管理器：npm（提交包含 `package-lock.json` 锁文件）
- Java：JDK 17 + Maven 3.6+（Back-end 项目；本仓库内置工具链 `Back-end/tools/`，Windows 下设置 `JAVA_HOME` 与 `PATH` 即可使用）
- Python：3.10+（Crawler 与 StreamingAPIDemo 项目，开发验证版本为 3.12）
- 环境变量：四个项目均无需任何环境变量即可运行
- 外部服务：无。Front-end 页面独立运行；Back-end 为纯本地服务；Crawler 需可访问 mitadmissions.org（评论数为 Disqus，本网络不可达时按默认 0 处理）；StreamingAPIDemo 完全本地（Figma REST API 仅用于开发阶段提取设计数据，数据已固化在仓库中）
