# App Market 重构计划：90% 成功率 + 统一显示

## Context

当前 App Market 存在四个核心问题导致用户体验差：
1. **网络失败无重试** — docker pull 超时直接报错，用户只能手动重来
2. **环境不匹配无预检** — 磁盘不够、L4T 版本不对，装到一半才失败
3. **命令本身有 bug** — 路径硬编码 `/home/seeed`、app-id 特例散落各处
4. **用户不知道怎么看结果** — 装完了不知道去哪看 demo 画面

目标：Docker 类 demo 一键部署成功率从当前 ~50% 提升到 90%，并在工具内直接看到 demo 画面。

---

## Phase 1: 可靠性引擎（最高优先级）

### 1A. 新建 `modules/apps/reliability.py`

核心逻辑：

- **错误分类器**：解析命令输出，区分瞬态错误（网络超时、502、DNS 失败）vs 永久错误（架构不兼容、磁盘满）
- **重试包装器**：网络类命令（含 `docker pull`/`wget`/`apt-get`/`pip install`/`git clone`）失败时自动重试 3 次，间隔 [5s, 15s, 30s]
- **预检函数 `preflight_check(runner, app)`**：
  - Docker daemon 是否运行
  - 磁盘空间是否满足 `required_disk_gb`
  - 内存是否满足 `required_mem_gb`
  - L4T 版本是否在 `jetpack_versions` 列表内
- **Docker 镜像源降级**：检测 registry-1.docker.io 是否可达，不可达时自动尝试国内镜像

### 1B. 修改 `modules/apps/page.py` — `_InstallThread.run()`

替换当前 292-306 行的线性执行循环：
- 每条命令执行前调用 reliability 引擎判断类型
- 网络类命令走重试逻辑
- 永久错误立即停止并给出明确中文提示
- 移除 line 298 的字符串启发式超时（`"Download" in cmd`），改用 app schema 中的 timeout 字段

### 1C. 给 23 个缺失 check_cmd 的 jetson-examples app 补上

统一格式：
```
bash -c 'export PATH=$HOME/.local/bin:$PATH && reComputer list 2>/dev/null | grep -qi "<example_name>"'
```

### 1D. 安装状态持久化

在 `core/config.py` 增加 `apps-state.json` 读写：
```json
{"jx-llama3": {"status": "installed", "completed_steps": [0,1,2], "total_steps": 3}}
```
支持断点续装：重试时跳过已完成步骤。

**新建文件：** `seeed_jetson_develop/modules/apps/reliability.py`
**修改文件：**
- `seeed_jetson_develop/modules/apps/page.py`
- `seeed_jetson_develop/modules/apps/data/jetson_examples.json`
- `seeed_jetson_develop/core/config.py`

---

## Phase 2: 统一显示系统

### 2A. SSHRunner 增加端口转发

在 `core/runner.py` 的 `SSHRunner` 类增加：
```python
def forward_local_port(self, remote_port: int) -> int:  # 返回本地端口
def close_forward(self, local_port: int): ...
def close_all_forwards(self): ...  # disconnect 时自动调用
```
实现：本地 socket server 线程 + paramiko `direct-tcpip` channel 桥接。

### 2B. 新建 `modules/apps/display_viewer.py`

QWebEngineView 封装：
- `show_web(url, title)` — 加载 web UI
- `show_vnc(host, port, title)` — 加载 noVNC 页面
- 工具栏：刷新、外部浏览器打开、关闭
- 状态栏：连接中 / 已连接 / 断开

集成方式：作为主窗口的浮动面板或 Apps 页面内的 overlay。

### 2C. App Schema 增加 `display` 字段

```json
"display": {
  "type": "web|vnc|log",
  "port": 8888,
  "url_template": "http://localhost:{local_port}/lab",
  "ready_check": "ss -tlnp | grep -q ':8888'",
  "ready_timeout": 30
}
```

分类：
- **web**: Jupyter(8888), ComfyUI(8188), Gradio apps(7860), Node-RED(1880)
- **vnc**: Depth Anything V3, OpenCV demos, RViz — 走 noVNC 6080
- **log**: Ollama, LLM 推理 — 保持当前终端对话框

### 2D. noVNC 按需部署

运行 `display.type == "vnc"` 的 app 时：
1. SSH 检查 `systemctl is-active seeed-novnc.service`（<1s）
2. 未运行则调用现有 `desktop_remote.py` 的部署逻辑
3. 确认 6080 端口监听后，建立 SSH 隧道，打开 WebView

### 2E. 运行流程串联

`_on_run_done(success=True)` 之后：
1. 读取 app 的 `display` 配置
2. 轮询 `ready_check` 直到成功或超时
3. 建立端口转发
4. 打开 display_viewer

**新建文件：** `seeed_jetson_develop/modules/apps/display_viewer.py`
**修改文件：**
- `seeed_jetson_develop/core/runner.py`
- `seeed_jetson_develop/modules/apps/page.py`
- `seeed_jetson_develop/modules/apps/data/apps.json`
- `seeed_jetson_develop/modules/apps/data/jetson_examples.json`
- `requirements.txt`（加 `PyQtWebEngine>=5.15.0`）

---

## Phase 3: Schema 清理 + 去除硬编码

### 3A. 替换 `/home/seeed` → `$HOME`

影响：`apps.json` 中 `yolov26-dual-gmsl` 条目。

### 3B. 移除 DA3 特例

- 删除 `registry.py` 中 `_DA3_RUN_CMDS` 和 `if app.get("id") == "jx-depth-anything-v3"` 分支
- 删除 `page.py` `_InstallThread.run()` 中 DA3 SFTP 上传逻辑（200-290 行）
- 将 DA3 的完整 run_cmds 直接写入 jetson_examples.json

### 3C. 新建 `modules/apps/schema.py` — JSON Schema 校验

`validate_app(app) -> list[str]` 在 load_apps() 时调用，开发模式下打印警告。

### 3D. 命令支持结构化格式（向后兼容）

```json
"install_cmds": [
  {"cmd": "docker pull ...", "timeout": 3600, "retry": true},
  "simple string cmd still works"
]
```

**新建文件：** `seeed_jetson_develop/modules/apps/schema.py`
**修改文件：**
- `seeed_jetson_develop/modules/apps/registry.py`
- `seeed_jetson_develop/modules/apps/data/apps.json`

---

## 验证方案

### Phase 1 验证
- 断网测试：安装过程中断开网络，确认重试 3 次后给出明确错误
- 磁盘不足测试：在磁盘满的设备上安装，确认预检拦截
- 续装测试：安装到第 3 步时关闭工具，重新打开确认从第 4 步继续
- 状态检测：连接设备后确认所有 26 个 app 都能正确检测已装/未装

### Phase 2 验证
- 端口转发：`forward_local_port(8888)` 后 `curl localhost:<port>` 能通
- WebView：Windows 上 QWebEngineView 正常加载 noVNC 页面
- 端到端：运行 Jupyter → 自动转发 → 工具内看到 Jupyter Lab 界面
- VNC 端到端：运行 DA3 → 自动部署 noVNC → 工具内看到 OpenCV 画面

### Phase 3 验证
- `grep -r "/home/seeed" modules/apps/data/` 返回空
- DA3 在移除特例后仍能正常安装和运行
- `validate_app()` 对所有 app 返回空错误列表

---

## 实施顺序建议

先做 Phase 1（1-2 天）→ 立即提升成功率
再做 Phase 2A+2B（1-2 天）→ 解决"看不到结果"
然后 Phase 2C-2E（1 天）→ 串联显示流程
最后 Phase 3（半天）→ 清理技术债
