# 完整网页版部署

此部署运行原有FastAPI、FFmpeg、Whisper、Demucs和本地Qwen，包含上传、字幕、逐词编辑、逐句录音/补录、建议、分离和真实导出。网页只通过HTTPS隧道暴露；模型端口和原来的8767私有工作台不对公网开放。

## 当前服务器

```bash
python deploy/manage.py status
```

查看 `data/deploy/runtime/tunnel.json` 中的 `url`。它是当前公网入口，无需SSH转发。`url + /api/ready`应为ready；部署包保存在服务器`data/deploy/koubo-web-runtime.tar.gz`，由维护者通过SSH/SFTP领取，不对公网提供源码包下载。

三个用户级systemd服务：`koubo-demo-model`（8783）、`koubo-demo-web`（8768）、`koubo-demo-tunnel`。已启用开机启动，进程异常退出会自动重启；当前用户Linger=yes，退出终端不会停止服务。数据持久化在`data/deploy/public-data`，与原项目分开。

[Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)提供临时HTTPS域名，无需账号。隧道进程重建后域名会改变，也没有生产可用性保证；网页或模型进程单独恢复不会重建隧道。需要固定域名时，在自己的域名上使用命名隧道或`Caddyfile.example`，并提供域名/DNS配置。未购买域名或服务。

## 迁移/重新部署

部署包包含代码、构建好的网页和授权样例，不包含私人项目、浏览器Cookie、模型权重或虚拟环境。目标为Linux x86_64，Python≥3.9、FFmpeg/ffprobe、CMake和C/C++编译器。

```bash
tar -xzf koubo-web-runtime.tar.gz
cd koubo-web
python deploy/bootstrap.py
python deploy/manage.py build
python deploy/manage.py install
python deploy/manage.py status
```

首次bootstrap按锁定依赖和模型清单准备运行环境，下载/编译耗时取决于网络与CPU；已有正确模型会复用。项目源码已有Node构建脚本时需要Node20以上；运行包已含静态网页，无需Node。

用户级systemd需可用；需跨退出/重启持续运行时由服务器管理员为该用户开启linger。新建的只是本项目命名的服务，不修改其他服务。固定域名反向代理参考[Caddy官方HTTPS说明](https://caddyserver.com/docs/automatic-https)，原站保持监听127.0.0.1:8768。

## 更新和维护

- 更新：`python deploy/manage.py build`创建按内容哈希命名的代码快照；`install`更新并重启本项目服务，隧道地址随之变化。
- 仅重启网页：`python deploy/manage.py restart-web`，数据保留，隧道地址保持。
- 停止：`python deploy/manage.py stop`。日志：`journalctl --user -u koubo-demo-web`及`data/deploy/runtime/tunnel.log`。
- 清理或备份前先停止本项目服务，再备份完整`data/deploy/public-data`。没有自动删除用户项目的定时任务；不要删除models或旧8767数据目录。
- 单次视频90MB/180秒；补录30MB/60秒。部署默认每会话10项目、全局50项目、最多3个处理任务、10GB数据预算。超限给出可重试提示，已有编辑仍可查看和修改。参数在生成的web服务Environment中，部署可按服务器容量调整。
- `.service`文件和当前公网URL均生成在被Git忽略的data/deploy中；发布到仓库的是模板、打包/安装程序与验证说明。

公开版本APP_MODE=hosted会开放完整上传/处理，原APP_MODE=public仍是禁止上传的样例模式。HTTPS同源请求校验、请求体上限和任务/项目准入只针对hosted生效。该配置用于受限公开Demo，不声称完成大规模生产部署审计。
