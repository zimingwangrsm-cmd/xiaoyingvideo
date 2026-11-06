# 口播精简 V2

本机视频转写、字幕精修、词级删除、整句重排、人工补录和逐项建议。V1的MP4+SRT导入、必留、撤销、真实导出和版本保护继续可用。

## 启动

Web服务沿用现有Python依赖。语音依赖使用独立`.venv-v2`，模型在被Git忽略的`models/`。

```bash
bash scripts/setup_v2.sh
python scripts/prepare_real_samples.py
```

本轮使用llama.cpp提交版本见`deliverables/v2/runtime_manifest.json`。本机GCC 7不能编译该版本，实际用已安装的GCC 9构建：

```bash
git -c http.proxy= clone https://github.com/ggml-org/llama.cpp.git data/tools/llama.cpp
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
7. 上传WAV/MP3/M4A补录，试听后确认。短音频补尾部静音，过长拒绝；保持画面长度，不处理口型。需要保留BGM时先做人声分离。
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
