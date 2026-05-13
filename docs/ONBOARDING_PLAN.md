# Seeed Jetson Develop Tool - 首次启动引导界面规划

## 概述
为客户端添加一个精美的多步骤引导界面（Onboarding / First-Run Guide），帮助新用户快速上手使用。引导在客户端首次打开时自动弹出，支持动画效果、步骤导航、关闭和"不再显示"功能。

---

## 引导流程（共 5 步）

### Step 1: Welcome — 欢迎
**内容：**
- 应用 Logo 缩放进入动画
- 标题："Welcome to Seeed Jetson Develop Tool"
- 副标题："Your all-in-one workspace for Jetson development"
- 简短介绍："Let's get you set up in just a few steps."

**动画：**
- Logo: `scale(0.5) → scale(1.0)` + `opacity(0) → opacity(1)`，duration 600ms，easing `OutBack`
- 标题: 从下方 `translateY(30px) → translateY(0)` + fade in，delay 200ms
- 副标题: 同上，delay 350ms

---

### Step 2: Connect Your Device — 设备连接
**内容：**
- 图标：🔌 USB-C / Type-C 连接线图标
- 标题："Connect Your Jetson Device"
- 说明文字：
  - "Use a USB-C cable to connect your Jetson device to your computer."
  - "Make sure the device is powered on and in recovery mode if needed."
- 提示标签："💡 Tip: For reComputer series, simply connect the Type-C port to your PC."

**动画：**
- 图标: 从左侧 `translateX(-50px) → translateX(0)` + fade in，duration 500ms
- 标题: 从右侧滑入，`translateX(50px) → translateX(0)`，delay 150ms
- 说明文字: 逐行 fade in，stagger 100ms
- 提示标签: 底部弹出 `translateY(20px) → translateY(0)`，delay 500ms

---

### Step 3: Flash Firmware — 刷机指引
**内容：**
- 图标：⚡ 闪电/刷机图标
- 标题："Flash the Firmware"
- 说明文字：
  - "Select your device model from the Flash page."
  - "Download the appropriate BSP and click Flash to burn the system image."
  - "Wait for the progress to complete — it's fully automated!"
- 提示标签："💡 The tool supports JetPack 5/6 for reComputer and reServer series."

**动画：**
- 图标: 旋转进入 `rotate(-15deg) → rotate(0)` + scale，duration 500ms
- 步骤文字: 左侧依次滑入，stagger 120ms
- 进度条示意图: 宽度从 0% → 100% 动画，duration 800ms，delay 400ms

---

### Step 4: Remote Access — 远程连接
**内容：**
- 图标：🖥️ 远程桌面 + SSH 终端图标
- 标题："Connect Remotely"
- 说明文字：
  - "Use Remote Desktop for a graphical interface to your Jetson."
  - "Or use SSH for command-line access directly from the tool."
  - "No extra software needed — everything is built in!"
- 两个功能卡片并排：Remote Desktop | SSH Terminal

**动画：**
- 图标: 从中心放大 `scale(0.3) → scale(1.0)`，duration 500ms，easing `OutBack`
- 标题: fade in，delay 200ms
- 两个功能卡片: 从下方交错滑入，左侧 delay 300ms，右侧 delay 450ms

---

### Step 5: Explore & Enjoy — 探索应用和 Skills
**内容：**
- 图标：🚀 火箭/探索图标
- 标题："Explore Apps & Skills"
- 说明文字：
  - "Install popular AI applications from the App Market with one click."
  - "Discover and run Skills to automate your Jetson workflows."
  - "From LLM inference to computer vision — it's all here."
- 行动号召："You're all set! Click 'Get Started' to begin your journey."
- 最终按钮："Get Started"（绿色主按钮，替代 Next）

**动画：**
- 图标: 从底部 `translateY(40px) → translateY(0)` + `rotate(-5deg) → rotate(0)`，duration 600ms
- 标题: fade in + scale，`scale(0.95) → scale(1.0)`，delay 200ms
- 说明文字: 逐行 fade in，stagger 100ms
- 行动号召: 发光效果 `opacity(0.6) → opacity(1.0)` + 文字颜色闪烁绿色，delay 600ms
- Get Started 按钮: 脉冲动画（scale 1.0 → 1.05 → 1.0），循环 2 次，delay 800ms

---

## 界面布局结构

```
┌─────────────────────────────────────────────────────────────┐
│  [X] Close                                    [□] [─]       │  <- 可选自定义标题栏
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌───────────────┐                        │
│                    │   Content     │  <- 步骤内容区域        │
│                    │   (Animated)  │     居中，最大宽度      │
│                    └───────────────┘                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ○ ○ ● ○ ○        [Back]      [Next]                       │  <- 进度指示器 + 导航按钮
│                                                             │
│  ☑ Don't show again                              Skip       │  <- 复选框 + 跳过链接
└─────────────────────────────────────────────────────────────┘
```

---

## 动画系统总览

| 动画类型 | 用途 | 参数 |
|---------|------|------|
| Fade In/Out | 页面切换、文字出现 | `opacity: 0→1`, duration 400ms |
| Slide Horizontal | 页面左右滑动切换 | `translateX: ±60px → 0`, duration 450ms |
| Scale Pop | Logo、图标进入 | `scale: 0.5→1.0`, easing `OutBack`, duration 500ms |
| Stagger Fade | 列表项依次出现 | 每项 delay +100ms |
| Progress Fill | 进度条/指示器 | `width: 0%→100%`, duration 600ms |
| Glow Pulse | 强调文字、按钮 | `opacity` 脉冲 + 阴影扩散 |

### 页面切换动画（Next/Back）
- **向前 (Next)**: 当前页 `slideLeft + fadeOut`，新页 `slideRightIn + fadeIn`
- **向后 (Back)**: 当前页 `slideRight + fadeOut`，新页 `slideLeftIn + fadeIn`
- Duration: 400ms
- Easing: `QEasingCurve.OutCubic`

### 步骤指示器动画
- 激活步骤: 圆点 `scale(1.0) → scale(1.3) → scale(1.1)`，颜色变为绿色
- 已完成步骤: 圆点变为实心绿色，可添加 ✓ 图标
- 过渡: `background-color` 渐变，duration 300ms

---

## 交互行为

### 按钮状态
| 场景 | Back | Next | Close |
|-----|------|------|-------|
| Step 1 | Disabled | "Next →" | Visible |
| Step 2-4 | "← Back" | "Next →" | Visible |
| Step 5 | "← Back" | "Get Started ✓" (Primary) | Hidden |

### "不再显示" (Don't show again)
- 底部左侧放置 `QCheckBox`
- 勾选后，关闭引导时写入配置：`onboarding_dismissed = true`
- 下次启动不再自动显示
- 用户仍可从菜单中手动打开：Help → First Run Guide

### 键盘导航
- `→` / `Space` / `Enter`: Next
- `←`: Back
- `Esc`: Close

---

## 技术实现

### 新增文件
- `seeed_jetson_develop/gui/widgets/onboarding_guide.py` — 引导界面主组件
- `seeed_jetson_develop/locales/en/onboarding.json` — 英文翻译
- `seeed_jetson_develop/locales/zh-CN/onboarding.json` — 中文翻译

### 修改文件
- `seeed_jetson_develop/core/config.py` — 添加 `get_onboarding_dismissed()` / `set_onboarding_dismissed()`
- `seeed_jetson_develop/gui/main_window_v2.py` — 在 `main()` 或 `MainWindowV2.__init__` 后显示引导

### 样式
- 复用 `theme.py` 的深色主题颜色系统
- 无边框对话框（`Qt.FramelessWindowHint`）
- 圆角卡片（radius 16px）
- 绿色强调色用于进度和主按钮
- 半透明背景遮罩（`rgba(0,0,0,0.75)`）
