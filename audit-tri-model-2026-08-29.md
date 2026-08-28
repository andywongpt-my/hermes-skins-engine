# hermes-skins-engine 审计报告（2026-08-29）

审计方式：AGY 双模型独立审计（gemini-3.1-pro-high + gemini-3.7-flash-high，无交叉污染）+ Meow 源码通读与运行时实测（第三视角）。所有 CRITICAL/HIGH 发现均已 grep/运行验证，不采信未验证声明。
仓库：https://github.com/andywongpt-my/hermes-skins-engine（v0.1.0，1331 LOC）
本地克隆：/home/meow/tmp/hermes-skins-audit

---

## 一、BUG（按严重度排序，全部已验证）

### 🔴 B1. `hex_to_hsl()` 饱和度/亮度解包互换 —— 全库最重的 bug（根因级）
- 证据：`src/hermes_skins/generators.py:26` — `h, s, l = colorsys.rgb_to_hls(r, g, b)`
- Python `colorsys.rgb_to_hls` 返回契约是 **(h, l, s)**（lightness 在第 2 位），代码按 (h, s, l) 接收 → **s 实际是亮度、l 实际是饱和度**，全引擎所有 HSL 派生全部失真。
- 实测（#CC0033 asuka 红）：真值 L=0.40/S=1.00，`hex_to_hsl` 返回 (345.0, 0.4, 1.0) ✓ 实锤互换。
- 连锁后果：
  - **asuka（默认模板）与 berserk 状态栏对比度仅 1.02:1（完全不可读）**：status_bg=#BBA9AD 淡粉 + text=#B8ACAF。其余 6 模板侥幸 5.2-8.6:1（中饱和底色侥幸过关）。
  - 互补色 accent 失效：asuka `ui_accent` 应为互补绿，实际生成 `#FFFEFE`（近白）。
- 修复后模拟（解包纠正）：accent=#00CC99 真互补绿，status contrast 14.14:1。
- ⚠️ 修复影响面：所有 8 模板生成色会变（asuka 淡粉表面 → 深红黑，更贴 EVA-02 设定）；asuka banner 艺术的硬编码粉色需微调但结构存活。**当前 Hermes active skin 是 asuka，修复会改变 TUI 观感，需 Andy 确认。**

### 🔴 B2. `validate()` 放行非法 hex，preview 先渲染后校验 → 未捕获崩溃
- 证据：`core.py:181`（只查 `#` 前缀 + 长度 7/9，不查字符合法性，`#ZZZZZZ` 通过）；`preview.py:11-19` `_fg()` 直接 `int(h[0:2],16)`。
- 实测：ui_accent="red" 的皮肤 → `render_preview` 抛 `ValueError: invalid literal for int() with base 16`，且崩溃发生在 `skin.validate()` 输出警告**之前**，用户永远看不到校验提示。
- 修复：validate 用 `^#[0-9a-fA-F]{6,8}$` 严格正则；`_fg()`/`hex_to_hsl()` 加安全回退。

### 🟠 B3. seele 模板字典键 typo `"waiting_faces:"`（多冒号）
- 证据：`generators.py:549`。实测：`generate_from_template("seele").spinner.waiting_faces` 落回通用 `['(·)','(◦)']`，❒❑❏ 单体几何 faces 永远不生效。两个模型均未抓到 typo 本体（Flash 抓到了），静默降级无任何告警。

### 🟠 B4. shinji spinner 面 `"◁)"` 缺左括号
- 证据：`generators.py:329`。实测确认：`['(▶)', '◁)', '(◯)', ...]`，动画帧不对称。

### 🟠 B5. `status_bar_bad` 从主题基色派生，违反语义色约定
- 证据：`generators.py:103`。nerv（绿底）→ status_bad 是亮绿"坏"状态；seele（近黑）→ 深灰失义。ui_ok/ui_error/ui_warn 都是固定语义色，唯独 bad 从基色派生。
- 修复：固定 `#FF8C00` 橙或语义偏移。

### 🟠 B6. `preview` 无参数时：帮助文本说"显示 active skin"，实际倾倒全部 8 模板（800+ 行）
- 证据：`cli.py:90-99`。双模型共识。修复：读 `~/.hermes/config.yaml` 的 `display.skin`；加 `--all` 显式倾倒。

### 🟠 B7. banner 艺术的 Rich 标签在 preview 里原样泄漏
- 证据：`generators.py:188+` 用 `[bold #C98293]…[/]` Rich 标记，`preview.py:69-79` 直接 print，不解析。实测确认 raw 标签出现在输出中。修复：正则转 ANSI（`[bold #HEX]` → `\033[1;38;2;R;G;Bm`）。

### 🟡 B8. `--harmony` 非法值静默回退
- 证据：`cli.py:167` + `generators.py:82-83` else 分支。`custom --harmony xxx` 不报错，静默生成单色系。

### 🟡 B9. `install` 原样拷贝不校验 + 文件名 stem 与 skin.name 双轨
- 证据：`cli.py:200-211`（不 `Skin.load`、不 validate，坏 YAML 直接进 `~/.hermes/skins/`）；`cli.py:55` 用文件 stem 做 key 而非内部 `name` 字段 → 重命名文件后 `preview/switch/export` 键名不一致。

### 🟡 B10. 9 位 hex alpha 通道静默丢弃
- 证据：`core.py:181` validate 允许 9 位，`generators.py:25` 只解析前 6 位。`#RRGGBBAA` 输入 alpha 无声丢失。

### 🟡 B11. 零测试、零 CI
- 1331 LOC 颜色引擎无一个测试、无 `.github/workflows/`。色数回归（如 B1 这种）完全无防护网。

### 🟡 B12. preview 工具图标行不换行
- `preview.py:64` 14 个 tool emoji 拼一行，窄终端溢出（自查发现，随 B7/F3 一起修）。

---

## 二、新功能机会（去重合并后 15 项）

| # | 功能 | 价值 | 规模 | 来源 |
|---|---|---|---|---|
| F1 | **WCAG 对比度引擎**：relative_luminance + contrast_ratio，`validate()` 内置关键色对检查（status_bar_text/bg、prompt/背景、completion_current/meta_bg），<4.5:1 自动提亮/压暗 | 高 | M | 共识（Pro+Flash）|
| F2 | **亮色终端双模式**：`generate_palette(mode="dark|light")`，light 模式反转派生方向（bg L∈0.92-0.97，文字 L∈0.10-0.22），CLI `--mode` | 高 | M | Flash（+Pro 方向）|
| F3 | **交互式选皮 TUI**：`hermes-skins picker`，上下键切换实时渲染预览（纯 tty raw mode 可零依赖） | 高 | M | Pro |
| F4 | **watch 实时预览**：`hermes-skins watch <file>`，mtime 轮询，改 YAML 即时刷新（皮作者刚需） | 高 | M | Pro |
| F5 | **`hermes-skins diff A B`**：29 槽位并排色块对比 + ΔE 高亮变化槽 + branding/spinner 差异 | 中 | S | 共识 |
| F6 | **Hermes 原生配置打通**：`list` 标注 `* (active)`、`preview` 无参默认 active、`switch` 无 hermes CLI 时直写 `~/.hermes/config.yaml` 回退 | 高 | S | 共识 |
| F7 | **CRUD 全生命周期**：`uninstall/rename/clone`（rename 同步内部 name 与文件名，顺带修 B9 双轨） | 高 | S | Flash |
| F8 | **URL/Gist 远程安装**：`install <url>` 用 urllib 零新依赖拉取 + validate 后落盘 | 中 | M | 共识 |
| F9 | **banner 艺术调色板同步**：硬编码 hex → `{accent}/{dim}/{bright}` 占位符，`generate_from_template` 动态注入（顺带修 B7） | 中 | M | 共识 |
| F10 | **NO_COLOR + 终端能力回退**：尊重 `$NO_COLOR`/非 tty 剥离 ANSI；truecolor→256/16 色近似 | 中 | S | Flash |
| F11 | **扩展和谐**：tetradic/square/pastel/neon + 次级色相分配给 ui_label/session_label/selection_bg | 中 | M | Flash |
| F12 | **schema 版本化 + 未知键保留**：`schema_version/author/tags/extra` 字段，round-trip 不丢社区皮肤元数据 | 中 | S | Flash |
| F13 | **`validate` CLI 子命令**：`hermes-skins validate [NAME|--all]`，退出码可脚本化，配 pre-commit | 中 | S | Flash |
| F14 | **pytest 测试套 + GitHub Actions CI**：core/generators/CLI(CliRunner)/preview 四模块，3.10-3.13 矩阵 | 高 | M | 共识 |
| F15 | **random/custom 动态 tool emoji**：从选中 faces 池随机分配，摆脱千篇一律 DEFAULT | 低 | S | Pro |

---

## 三、共识分层（置信度参考）

- **Tier 1 双模型共识**（6 项）：preview 无参行为、status_bad 语义、对比度/WCAG、banner 硬编码漂移、diff、配置打通/switch 回退、tests+CI、fetch
- **Tier 2 单模型 + 已验证**（9 项）：seele typo、shinji 面、Rich 泄漏、#ZZZZZZ 洞、harmony 回退、install 校验、亮色模式、picker、watch、schema 版本化、扩展和谐、validate cmd、CRUD、alpha 丢弃、stem 双轨、动态 emoji
- **Tier 3 仅自查实测**（模型双方都漏）：**B1 hex_to_hsl s/l 互换根因**（两模型都只报了"对比度差"的症状层）、B12 溢出、banner 艺术与 buggy 调色板同调的观感影响

> 备注：B1 恰好证明三视角审计的价值——两个模型均停在症状层（"对比度 1.02:1"），没做数值根因分析。修复 B1 时应连带动 WCAG 引擎（F1）做全模板回归门禁。

---

## 四、建议实施顺序

> **实施记录（2026-08-29）：** P0 已完成（commit d81c37e + 后续审计修复 commit）。B1-B12 全部修复；AGY post-dev diff 审计（Flash 3.7）发现的 6 个新问题（Enum 泄漏、custom 坏 hex 未捕获、_rgb 非字符串崩溃、install 消息泄漏原始 name、SameFileError、hsl_to_hex 1-bit 截断）也已全部修复并回归验证。终态：8/8 模板 + 16 极端基色 + 20 随机种子全部 WCAG AA ≥4.5:1，CLI 全错误路径干净退出。P1/P2 功能机会（WCAG validate 子命令、测试+CI、picker/watch/diff、CRUD、亮色模式、URL 安装、banner 调色板同步等）见上文清单，待排期。

1. **P0（一次提交修完，~1-2h）**：B1（解包纠正+8 模板重生成+对比度复验）、B2（严格 hex 正则+安全回退）、B3、B4、B5、B6、B7、B9(install 校验部分)
2. **P1（质量地基，~2-3h）**：F14 测试+CI（给 B1 类回归上锁）、F1 WCAG 引擎进 validate、F6 配置打通、F13 validate 子命令、F10 NO_COLOR
3. **P2（体验增值）**：F3 picker、F4 watch、F5 diff、F7 CRUD、F2 亮色模式、F8 URL 安装、F9 banner 同步、F12/F11/F15

⚠️ P0 落地会改变 asuka（当前 active）的 TUI 观感（淡粉 → 深红黑战术风），发布前需 Andy 过目。
