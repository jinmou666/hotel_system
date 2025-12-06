# Vue 3 + Vite
## 项目说明
本目录为「酒店空调管理系统」前端代码，包含空调面板、前台管理、监控大屏三大核心模块。

## 运行依赖
- Node.js（建议v18+，需配置环境变量确保npm命令可识别）
- npm（随Node.js自动安装）

## 本地运行步骤
1. 进入前端目录：`cd front`
2. 安装项目依赖：`npm install`
3. 启动开发服务器：`npm run dev`
4. 访问地址：http://localhost:5173

## 打包部署
1. 打包生成静态文件：`npm run build`
2. 打包产物位于`dist`目录，可部署至Nginx/Apache等Web服务器

## 核心功能模块
- 空调面板：开关机、温/风速调节、费用显示
- 前台管理：入住/退房表单提交
- 监控大屏：房间状态实时展示

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).