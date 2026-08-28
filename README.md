# CS2 配置备份工具 (CS2BackupTool)

一个 Windows 下的《反恐精英 2》(CS2) 备份小工具（**白色主题**）。  
自动识别 Steam 账户（圆形头像 + 昵称 + 账户 ID），按用户备份 **730 全部数据** 或 **游戏 CFG 配置** 为 zip 包，支持跨用户恢复（恢复前自动备份目标现有配置并标明来源），右侧内置 **AI 逐行注释 cfg** 面板。  
打包为单 exe，免安装。

> 🌐 **官网**：<https://chenyanglt.github.io/CS2BackupTool>  
> ⬇ **下载**：<https://github.com/ChenyangLT/CS2BackupTool/releases/latest>

---

## ✨ 功能一览

| 需求 | 实现 |
| --- | --- |
| 白色主题 | 全局浅色 QSS，蓝色主按钮，舒适的字体与按钮间距 |
| 自动识别账户 + 头像 | 解析 `loginusers.vdf`（兼容新旧格式）+ `userdata`；头像为**圆形** |
| 动态头像（尽力而为） | 本地无头像时，后台抓取 Steam 社区头像缓存到本地；可在设置配置**代理**加速 |
| 多账户居中显示 | 卡片**上下左右自适应居中**，随窗口缩放自动重排 |
| 每页最多显示数可配置 | 设置里 1–9 个/页，超过自动**分页**（上一页/下一页） |
| 名称在上 ID 在下 | 卡片显示昵称（上）+ 🆔 账户ID（下，如 `1506549601`）+ 730 状态 |
| 右键头像快捷菜单 | 🌐 打开 Steam 主页 / 📦 打开 730 文件夹 / 📁 打开 cfg 文件夹 |
| 点击头像定向备份 | 点击进入该用户备份管理，个人信息**完整显示**（昵称/账号/账户ID/SteamID64/路径） |
| 备份 730 与 cfg 分开 | 两个独立按钮：「📦 备份 730 全部数据」「📁 备份 CFG 配置」 |
| cfg 指游戏目录 | cfg = `<库>\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg`（自动定位所有 Steam 库） |
| zip 打包 + 指定目录 | 每次备份生成 `昵称_类型_时间戳.zip`（含 manifest 元数据）；目录可在设置指定 |
| 压缩等级可配置 | 设置里 0–9 级（0 最快 / 9 最小） |
| 显示时间与大小 | 备份记录表格展示 类型/原用户/备注/时间/大小/文件数 |
| 跨用户恢复 + 自动备份来源 | 恢复时可选任意用户；恢复前**自动把目标现有配置打包**，备注标明「🛡️ 恢复前自动备份（恢复来源: xx）」 |
| 备注自由编辑 | 「✏️ 备注」按钮或双击备注单元格编辑，写回 zip 内 manifest；恢复只能点「恢复」按钮，双击不再误触 |
| AI 注释 cfg | 右侧面板：复选框**展开显示** cfg 文本，点「开始注释」AI 逐行添加中文注释；上方 💾 保存 / 📄 另存为 / 📋 复制 |
| AI 复选框开关 | 设置中「🤖 AI 注释」为复选框，启用后才显示 API 配置 |
| 每页顶部返回按钮 | 用户管理页、设置页均有「🏠 返回」 |
| 恢复默认配置 | 设置界面「🔄 恢复默认」一键还原所有默认值 |
| 报错与调试 | 未捕获异常始终写 crash.log 并弹窗；调试日志在设置中开关（默认关），勾选框带对钩 |
| 单 exe | PyInstaller onefile，免安装 |

---

## 🚀 使用说明

1. 双击 `CS2BackupTool.exe`。程序自动识别 Steam 与 CS2 游戏 cfg 目录。
2. 主界面卡片**居中**显示；超过每页上限时下方出现分页导航。
3. **右键头像**可快速打开 Steam 主页 / 730 文件夹 / cfg 文件夹。
4. 点击头像进入该用户备份管理：
   - **备份**：「📦 备份 730 全部数据」或「📁 备份 CFG 配置（游戏 cfg）」。
   - **恢复**：在「备份记录」选中一条点「恢复」，730 可选任意目标用户，cfg 恢复到游戏 cfg 目录；恢复前自动备份现有配置。
   - **AI 注释**：在右侧面板选 cfg 文件，勾选「📂 展开显示」，点「🤖 开始注释」，结果可 💾 保存 / 📄 另存为。

---

## ⚙️ 设置项

| 分组 | 配置 |
| --- | --- |
| 🗄️ Steam 与备份目录 | Steam 安装目录、备份存储目录 |
| ⚙️ 显示与压缩 | 每页最多显示用户数（1–9）、zip 压缩等级（0–9） |
| 🌐 网络 | 代理服务器（用于快速获取头像 / AI 请求） |
| 🤖 AI 注释 | 复选框启用开关、API 地址、API Key、模型、温度（+ 测试连接） |

AI 默认走 DeepSeek（`https://api.deepseek.com/v1` / `deepseek-chat`），也可填任意 OpenAI 兼容接口。  
Key 仅保存在本机 `%APPDATA%\CS2BackupTool\config.json`。

---

## 📁 数据位置

| 内容 | 路径 |
| --- | --- |
| Steam 用户数据 | `<Steam>\userdata\<账户ID>\` |
| CS2 (730) 数据 | `<Steam>\userdata\<账户ID>\730\` |
| 游戏 cfg（本工具所指） | `<库>\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg\` |
| 本工具配置 | `%APPDATA%\CS2BackupTool\config.json` |
| 动态头像缓存 | `%APPDATA%\CS2BackupTool\avatars\<SteamID64>.jpg` |
| 备份目录 | 默认 exe 旁 `Backups`（可在设置修改） |

---

## 🛠️ 开发者构建

```powershell
.\build.ps1            # 一键打包（安装依赖 + 生成图标 + PyInstaller）

# 或手动：
pip install -r requirements.txt
python tools/make_icon.py
python -m PyInstaller --noconfirm --clean --onefile --windowed --name CS2BackupTool `
    --icon app.ico --add-data "app.ico;." main.py
```

自检（源码或 exe 均支持）：

```powershell
python main.py --selftest   # 核心逻辑自检 -> selftest_result.txt
python main.py --smoke      # 离屏 GUI 冒烟 -> smoke_result.txt
python tools/screenshot.py  # 渲染主界面/用户界面并截图（视觉校验用）
```

## 报错与调试

- 未捕获异常**始终**写入 `%APPDATA%\CS2BackupTool\logs\crash.log` 并弹出错误框（报错功能，默认开启）。
- 调试日志**默认关闭**，可在「设置 → 🐞 调试与日志」勾选开启，或加 `--debug` 启动；开启后写入 `app_YYYYMMDD.log`（含 DEBUG 级与 Qt 内部消息）。
- 开启调试日志后，备份 / 恢复 / AI 请求的失败与异常都会记录，便于排查。

## 注意事项

- **恢复前请先退出 Steam**，避免 730 文件被占用。
- 动态头像需联网（steamcommunity 可能被墙，配代理可改善）；失败会自动退回本地/占位头像。
- 部分杀毒软件可能对 PyInstaller 单文件程序误报，添加信任即可。
- 备份 zip 内的 `manifest.json` 记录类型/来源/备注，手动改名不影响识别。
