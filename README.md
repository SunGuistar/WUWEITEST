# 技术笔试作品集

本仓库用于集中保存个人完成的技术笔试题及其实现代码，涵盖前端开发、后端开发、AI 应用开发等技术方向。

各笔试项目独立组织，提供题目要求、技术栈、实现说明和运行方式，便于招聘人员和技术面试官快速查看与验证。

> 未来计划扩展后端开发、AI 应用开发等方向的笔试项目，后续按相同格式补充。

## 项目目录

| 目录 | 题目类型 | 简介 |
|---|---|---|
| [Front-end/](Front-end/) | 前端开发笔试 | 基于 Figma 设计稿高精度还原「上传简历」页面（React + TypeScript + Vite） |

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

## 运行环境

- Node.js：v20（开发验证版本为 v20.18，其他 Node 18+ 版本应兼容）
- 包管理器：npm（提交包含 `package-lock.json` 锁文件）
- 环境变量：无需任何环境变量即可运行页面与测试
- 外部服务：无。页面独立运行，不依赖 Figma Token 或任何后端服务（Figma REST API 仅用于开发阶段提取设计数据，数据已固化在仓库中）
