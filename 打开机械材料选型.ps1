$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root 'desktop_ui.ps1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script
Read-Host 'Press Enter to close'
