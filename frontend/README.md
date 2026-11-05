# 前端

本地采用原生 JavaScript ES modules、HTML 与 CSS。检查时 Node 20.20.0 可用，但离线缓存及已有工程缺少 ReactDOM、Vite、TypeScript，网络安装受环境限制；为保留完整 P0 工作流，改用无第三方依赖的实现。没有使用 CDN。

```bash
cd frontend
npm run check
npm run build
```

构建只做语法检查和静态文件复制，输出 `dist/index.html` 与 `dist/assets/`，由同源后端提供；无需 npm install。项目入口是 `src/app.js`，视图在 `src/views.js`，媒体快照与建议版本判断在 `src/model.js`。

浏览器仅在 localStorage 存项目 ID；匿名会话 Cookie、项目版本、时长、锁定限制与导出快照由后端验证。建议不会自动应用。轮询使用后端阶段及进度，不模拟完成百分比。
