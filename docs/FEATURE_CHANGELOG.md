# Feature 变更记录

> 每次 feature 更新在此记录，方便其他 agent 了解上下文并复刻。

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
