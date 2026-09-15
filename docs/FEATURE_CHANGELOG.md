# Feature 变更记录

> 每次 feature 更新在此记录，方便其他 agent 了解上下文并复刻。

---

## [2026-09-09] 全局彩色 emoji 字体修复

### 背景

Linux 上界面中大量 emoji（按钮 ⚡、搜索框 🔍、徽章 🤖、日志 ⏳ ✓ 等）渲染为
黑白。项目已有按标签处理的 `set_emoji_font_for_label`，但只对少数调用点生效，
绝大多数 QLabel / QPushButton / QComboBox / 日志框继承的是不含 emoji 回退链的
默认字体，被系统 fallback 成黑白字形。

### 方案

1. `theme.py` 的 `build_app_font()` 在非 Windows 平台把 `"Noto Color Emoji"`
   追加为字体族回退链（`font.setFamilies([ui, "Noto Color Emoji"])`）。
   应用启动时 `app.setFont(build_app_font(...))` 全局生效，所有继承默认字体
   的控件自动获得彩色 emoji。
2. 所有显式 `font-family:...monospace;` 的样式表（日志 / 终端区域）追加
   `'Noto Color Emoji'`，修复等宽区域内的 emoji。

已用离屏像素级验证：修复前 emoji 区域饱和色像素为 0（纯灰度），修复后
> 0（彩色）。Windows 不受影响（走系统 Segoe UI Emoji 引擎）。

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `seeed_jetson_develop/gui/theme.py` | `build_app_font()` 追加 emoji 字体族回退链 |
| `seeed_jetson_develop/gui/ai_chat.py` | 两处 monospace 样式表追加 emoji 字体 |
| `seeed_jetson_develop/modules/{skills,apps,devices,flash}/page.py` | monospace 样式表追加 emoji 字体 |
| `seeed_jetson_develop/modules/remote/{jetson_init,agent_install_dialog,net_share_dialog}.py` | monospace 样式表追加 emoji 字体 |

---

## [2026-09-09] NVIDIA Skills 分类（运行目标 + 使用场景）

### 背景

Skills 板块「⚡ 获取 NVIDIA Skills」弹窗通过 `npx skills add nvidia/skills --list`
只拿到 (name, description)，344 个技能平铺展示。用户无法区分哪些在 Jetson
上运行、哪些在 PC 开发机运行，也没有使用场景分类。

### 方案

新增前缀规则分类目录（参考官方仓库 https://github.com/nvidia/skills 的产品
族结构），两个维度：

- 运行目标：`jetson`（Jetson 设备）/ `pc`（PC 开发机）/ `both`（PC 与 Jetson
  均可，如 DeepStream / VSS / Holoscan / HSB 等边缘视频栈）
- 使用场景（9 类）：Jetson 设备与系统、视频 AI 与视觉分析、边缘大模型推理、
  大模型与生成式 AI、视觉模型训练 (TAO)、医疗影像、科学计算与加速计算、
  网络与 DPU (DOCA)、机器人与物理 AI、其他

弹窗内直接平铺可点击的 chips（而非下拉框）：「运行目标」单选 chips
（全部 / Jetson 设备 / PC 开发机）+「使用场景」chips（图标 + 名称 + 数量，
FlowLayout 自动换行，单选）；每行保留彩色目标徽章；列表按分类排序；
头部提示"所有技能均安装到本机 PC"。中英文均支持，刷新后自动重建并翻译。

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `seeed_jetson_develop/modules/skills/nvidia_catalog.py` | **新增**：前缀规则分类模块（`nvidia_category` / `nvidia_target` / `target_matches` 等） |
| `seeed_jetson_develop/modules/skills/page.py` | `_NvidiaSkillsDialog` 增加目标/场景 chips（`_FlowLayout` 自动换行）与行内目标徽章、按分类排序；文案改为中文源；修复 `_get_installed_nvidia_skills` 扫描 CWD 而非用户主目录的 bug |
| `seeed_jetson_develop/gui/runtime_i18n.py` | 新增分类相关 zh→en 映射（精确串 + 模式：安装进度、数量统计、图标分类项） |
| `seeed_jetson_develop/locales/{en,zh-CN}/skills.json` | 补缺失的 `skills.category.nvidia_skills` key |
| `tests/test_nvidia_skills_load.py` | 新增 `TestNvidiaCatalog`：目标/分类/筛选匹配测试 |

---

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
