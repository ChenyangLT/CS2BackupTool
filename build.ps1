# CS2 配置备份工具 - 一键打包脚本 (Windows)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host '==> [1/4] 检查依赖'
python -m pip show PySide6 *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host '    安装 PySide6 ...'
    python -m pip install -r requirements.txt
}

Write-Host '==> [2/4] 生成应用图标'
python tools/make_icon.py

Write-Host '==> [3/4] PyInstaller 打包 (onefile)'
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name CS2BackupTool `
    --icon app.ico `
    --add-data "app.ico;." `
    main.py

Write-Host '==> [4/4] 复制产物到项目根目录'
Copy-Item dist\CS2BackupTool.exe -Destination CS2BackupTool.exe -Force

Write-Host ''
Write-Host "打包完成: $PSScriptRoot\CS2BackupTool.exe"
Write-Host '自检: CS2BackupTool.exe --selftest'
