# Feature 变更记录

> 每次 feature 更新在此记录，方便其他 agent 了解上下文并复刻。

---

## [2026-04-22] GUI 多语言本地化（English / French / Spanish / German）

### 背景

V2 PyQt GUI 原本已有语言切换入口，但菜单只硬编码 `English` / `中文`，locale JSON 也只包含 `en` 和 `zh-CN`。用户安装后无法在 GUI 中选择 French、Spanish、German，也缺少统一的语言注册、系统语言初始化、locale 校验和安装包资源覆盖。

### 方案

沿用现有 JSON i18n 体系，不引入 Qt `.qm` 翻译链路。新增统一语言注册表，扩展配置层语言规范化和系统语言检测，让首次启动按 OS 语言选择支持的 locale，否则回退 English。新增 `fr`、`es`、`de` locale 目录，并保留 `zh-CN` 兼容现有用户。

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `seeed_jetson_develop/core/config.py` | 默认语言改为 `en`；新增 `SUPPORTED_LANGUAGES`；支持 `fr-FR/fr_FR`、`es-ES/es_ES`、`de-DE/de_DE`、`zh-CN/zh_CN` 等别名；未保存语言时读取 OS locale |
| `seeed_jetson_develop/gui/i18n.py` | 新增语言注册表和显示标签；`t()` 支持 `default=` fallback；locale 读取支持 `utf-8-sig` |
| `seeed_jetson_develop/gui/main_window_v2.py` | 语言菜单改为注册表驱动；切换后持久化；侧边栏/窗口宽度从 English-only 判断改为非中文长标签布局 |
| `seeed_jetson_develop/gui/runtime_i18n.py` | 旧运行时翻译层支持规范化语言和 English locale value fallback，兼容 lazy-loaded 页面和旧 widget 文案 |
| `seeed_jetson_develop/locales/fr`, `es`, `de` | 新增 French、Spanish、German locale JSON，覆盖现有 9 个 locale 文件 |
| `seeed_jetson_develop/locales/en`, `zh-CN` | 增补 app/skill data-backed keys、后台运行/取消对话框 keys；补齐 `remote.conn.btn.terminal` |
| `seeed_jetson_develop/modules/apps/page.py` | App 名称、类别、描述改为 key-based lookup，缺失时回退原始 catalog 文案 |
| `seeed_jetson_develop/modules/skills/page.py` | Skill 名称、描述改为 key-based lookup，缺失时回退原始 catalog 文案 |
| `seeed_jetson_develop/gui/ai_chat.py` | AI system prompt 按所选语言要求回答；Skills/Apps 上下文使用本地化 catalog 文案 |
| `seeed_jetson_develop/data/recovery_guides.py` / `modules/flash/page.py` | Recovery guide 对非中文语言使用英文 guide 字段，避免回退到中文 |
| `scripts/check_locales.py` | 校验所有 locale 目录；支持 UTF-8 BOM；报告 missing/extra keys |
| `setup.py` | legacy packaging 增加 `locales/*/*.json` |
| `docs/i18n/TERMINOLOGY.md` | 记录 NVIDIA/Jetson 术语基线和来源链接 |
| `tests/test_i18n.py` | 增加语言别名、OS fallback、保存语言优先级、translation default fallback 单元测试 |

### 术语基线

- 保留产品、SDK、协议、包名：Jetson、Orin、JetPack、L4T、BSP、CUDA、TensorRT、cuDNN、DeepStream、VPI、Riva、Isaac、NGC、SDK Manager、Docker、PyTorch、Jupyter Lab、VS Code、SSH、VNC/noVNC、RTSP、GMSL、NVMe、HDMI、USB、SHA256、jtop。
- UI 默认术语：FR `Flashage` / `Mode de récupération` / `Développement à distance`，ES `Flasheo` / `Modo de recuperación` / `Desarrollo remoto`，DE `Flashen` / `Wiederherstellungsmodus` / `Remote-Entwicklung`。

### 验证

```bash
python -m unittest tests.test_i18n -v
python scripts/check_locales.py
python -m compileall -q seeed_jetson_develop/gui seeed_jetson_develop/modules
python -m pip wheel . -w .tmp_wheel --no-deps
```

Wheel 检查确认 `en`、`fr`、`es`、`de`、`zh-CN` 每个 locale 目录都包含 9 个 JSON 文件。

## [2026-04-13] 跨平台 UI 参数分离（PlatformUI）

### 背景

应用在 Linux 和 Windows 上的 UI 表现差异较大：窗口大小、字体渲染、控件间距、阴影效果等在 Windows 上偏大或不协调。原因是 Qt 在不同 OS 上的 DPI 缩放机制和字体渲染引擎不同。

之前只在 `pt()` 函数里做了 Windows 0.80 的字体缩放，窗口尺寸、标题栏高度、侧边栏宽度等全部硬编码，没有平台区分。

### 方案

在 `theme.py` 中引入 `PlatformUI` dataclass，集中定义 Linux / Windows 两套 UI 参数。启动时通过 `sys.platform` 自动选择对应的参数实例。

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `seeed_jetson_develop/gui/theme.py` | 新增 `PlatformUI` dataclass、`_PLATFORM_LINUX`、`_PLATFORM_WINDOWS` 实例、`PLATFORM` 全局单例；`pt()` 改用 `PLATFORM.font_scale`；`make_card()` 改用 `PLATFORM.card_radius / shadow_*` |
| `seeed_jetson_develop/gui/main_window_v2.py` | import `PLATFORM`；窗口最小尺寸、标题栏高度、侧边栏宽度、品牌区高度、DPI 字体基准全部改为读取 `PLATFORM` 字段；`main()` 中窗口占屏比例和最大尺寸也使用 `PLATFORM` |

### PlatformUI 参数对照

| 参数 | Linux（基准） | Windows |
|------|:---:|:---:|
| `font_scale` | 1.0 | 0.80 |
| `win_width_ratio` | 0.85 | 0.78 |
| `win_height_ratio` | 0.88 | 0.82 |
| `win_min_w` | 1080 | 1024 |
| `win_min_h` | 720 | 680 |
| `win_max_w` | 1920 | 1800 |
| `win_max_h` | 1080 | 1020 |
| `titlebar_h` | 64 | 56 |
| `sidebar_w_zh` | 200 | 180 |
| `sidebar_w_en` | 220 | 200 |
| `sidebar_btn_h` | 44 | 40 |
| `card_radius` | 12 | 10 |
| `shadow_blur` | 28 | 22 |
| `shadow_y` | 6 | 4 |
| `shadow_alpha` | 80 | 70 |
| `btn_h` | 42 | 38 |
| `btn_h_small` | 36 | 32 |
| `dpi_base_pt` | 13 | 12 |
| `dpi_min_pt` | 11 | 10 |

### 使用方式

```python
from seeed_jetson_develop.gui.theme import PLATFORM, pt

# 读取平台参数
PLATFORM.titlebar_h   # Linux: 64, Windows: 56
PLATFORM.sidebar_w_zh # Linux: 200, Windows: 180

# pt() 自动按平台缩放
pt(13)  # Linux: 13, Windows: 10
```

### 扩展方式

如需支持 macOS，只需在 `theme.py` 中新增：

```python
_PLATFORM_MACOS = PlatformUI(
    font_scale=0.90,
    # ... 其他参数
)

def _detect_platform_ui() -> PlatformUI:
    if sys.platform == "win32":
        return _PLATFORM_WINDOWS
    if sys.platform == "darwin":
        return _PLATFORM_MACOS
    return _PLATFORM_LINUX
```

### 调试建议

Windows 上实际运行后，如果某些控件仍然偏大或偏小，直接调整 `_PLATFORM_WINDOWS` 中对应字段的数值即可，不需要改其他代码。
