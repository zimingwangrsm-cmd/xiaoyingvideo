# 口播精简 V2

当前审阅优化版与验收入口见根README和deliverables/optimization/ACCEPTANCE_GUIDE.md。本文保留安装/模型复现细节。

本机视频转写、字幕精修、词级删除、整句重排、人工补录和逐项建议。V1的MP4+SRT导入、必留、撤销、真实导出和版本保护继续可用。

## 启动

Web服务沿用现有Python依赖。语音依赖使用独立`.venv-v2`，模型在被Git忽略的`models/`。

```bash
bash scripts/setup_v2.sh
python scripts/prepare_real_samples.py
```

模型下载默认按验收清单固定revision与SHA256；仅显式传入`python scripts/download_models.py --update`才跟随上游更新。

本轮使用llama.cpp提交版本见`deliverables/v2/runtime_manifest.json`。本机GCC 7不能编译该版本，实际用已安装的GCC 9构建：

```bash
git -c http.proxy= clone https://github.com/ggml-org/llama.cpp.git data/tools/llama.cpp
git -C data/tools/llama.cpp checkout 4b77dee0524c64b8471869232e2958bd9589607d
cmake -S data/tools/llama.cpp -B data/tools/llama.cpp/build-gcc9 \
  -DCMAKE_C_COMPILER=/usr/bin/gcc-9 -DCMAKE_CXX_COMPILER=/usr/bin/g++-9 \
  -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build data/tools/llama.cpp/build-gcc9 --target llama-server -j 8
bash scripts/run_local_model.sh
```

另开终端启动Web服务。已有模型和素材时，无需重复下载或重新生成：

```bash
DATA_DIR=data/v2_demo PORT=8767 bash scripts/run_v2.sh
```

服务均只监听回环地址。远程浏览器只转发Web端口8767；模型端口8781无需转发。同一DATA_DIR只能启动一个服务实例。

## 使用流程

1. 选择真人样例，或只上传MP4让本机生成字幕；SRT可选。
2. 核对自动识别稿。口音、专名和低清音频可能识别错误，尤其要检查人名、地名、数字和否定词。
3. 每段点击“精修 / 补录”：整段字幕校对、逐词校对和口误备注分别保存。修改字幕不改声音。
4. 选择有实测时间戳的词语，删除或恢复对应音视频；整段校对文字需先恢复原字幕，再进行词级操作。
5. 上移/下移完整句组。必留片段不能删除内部词语，锁定会恢复该段已删除词。
6. 点击生成建议：查看本地模型的整体方针和逐项理由，可接受、拒绝或全部接受。需要新说法的改写进入待补录。
7. 上传WAV/MP3/M4A补录，试听后确认。每句最多60秒。短于原句补尾部静音，长于原句延长末帧，完整保留声音；不处理口型。需要保留BGM时先做人声分离。
8. 生成实际短片、检查切口，再下载MP4/SRT/记录或交接ZIP。ZIP可交给其他剪辑工具或开发者；其中JSON不是第三方编辑器原生工程文件。

## 模型与媒体来源

- faster-whisper medium，CPU int8，中文、VAD、词时间戳。只使用本地模型文件。
- Demucs htdemucs，人声/背景分离，CPU执行。分离结果供试听与转写；歌唱和多人重叠需要人工复核。
- Qwen2.5-7B-Instruct Q4_K_M，通过llama.cpp本机接口生成建议；结果必须校验ID和必留约束。模型失败会明确回退到规则建议。
- 两条真人语言分享来自Wikitongues，经Wikimedia Commons提供，媒体为CC BY-SA 4.0。作者、来源、变更和哈希见各样例manifest；衍生媒体沿用原许可。样例未作原作者背书。
- 旧合成样例的文件与哈希保持不变。重跑识别只会更新新的V2派生字幕，不应替换旧样例。

## 验证与报告

`tests/test_v2.py`使用工程视频核对实际帧顺序、声音频率、字幕映射、事务及版本保护；该层的推理桩明确仅用于确定性测试。

`scripts/check_v2_browser.cjs`访问真实Web服务，真正调用ASR、分离和本地模型，核对导入、修改、补录、渲染与下载。真实证据保存在`deliverables/v2/`。模型文件、大媒体与缓存不提交Git；交付包在本地生成。

词切点量化到30fps，分辨率约33毫秒；字幕文字修订不会让源音频说出新内容。同声线生成与口型同步留待后续版本。

## 运行预算与本轮证据

当前CPU推理固定8线程，Qwen上下文16384、单槽；验收机器性能不等同最低配置承诺。建议先准备16GB可用内存、20GB空闲磁盘作为安装规划值，实际还需为上传、原片、模型缓存和导出留空间。没有做最低硬件压测，安装下载时间取决于网络，不报固定保证。

本轮128.2秒素材的结构化建议实测199.9秒；不能换算成所有输入的固定速度。清单校验可运行 `python scripts/download_models.py`，已有正确文件只核对哈希。语音环境/模型预检由run_v2.sh执行，后台阶段与实际耗时在界面显示。当前不支持安全取消单个正在执行的CPU推理；服务退出可能等待任务，重启会标记中断任务，不会伪装完成。

项目JSON已在部署前备份到被忽略的data目录。恢复备份应先停服务，备份当前整个DATA_DIR，再恢复完整对应数据（JSON与媒体），不可只搬JSON到缺失媒体的目录。不要让两个实例共享同一DATA_DIR。

新浏览器回归使用 `scripts/check_optimization.cjs`：设置APP_URL指向隔离服务、TEST_DATA_DIR指向同一隔离数据目录，并配置Playwright/Chrome路径。多项建议fixture仅用于交互覆盖；新真实模型结果见optimization/showcase_validation.json。旧check_v2_browser/record_v2_walkthrough脚本按V2基线布局保留；复现历史录屏须使用其基线提交，不将旧脚本当本轮完整验收入口。

本轮录屏脚本 `scripts/record_optimization.cjs` 记录已生成结果的实际播放、切口试听和下载，使用私有验收项目状态，不在录屏中重复约200秒的推理。旧171.04秒录屏继续作为V2基线证据。
