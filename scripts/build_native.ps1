$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$installation = & $vswhere -latest -prerelease -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$installation) { throw 'MSVC x64 tools are required to build the native helper' }
& "$installation/Common7/Tools/Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
$output = Join-Path $root '.local/native'
New-Item -ItemType Directory -Force $output | Out-Null
Push-Location $output
try {
    & cl.exe /nologo /W4 /WX /O2 /MT /LD /std:c++17 /DUNICODE /D_UNICODE `
        "$root/native/helper.cpp" "$root/native/score_host.cpp" "$root/native/engine_identity.cpp" `
        "$root/native/plugin_host.cpp" "$root/native/automation_host.cpp" "$root/native/playlist_host.cpp" `
        "$root/native/plugin_state.cpp" "$root/native/project_host.cpp" "$root/native/audio_clip_host.cpp" `
        "$root/native/effect_host.cpp" `
        /link user32.lib bcrypt.lib /OUT:FruityCommanderHost.dll
    if ($LASTEXITCODE) { throw 'Native helper compilation failed' }
    & cl.exe /nologo /W4 /WX /O2 /MT /std:c++17 "$root/native/test_host.cpp" `
        /link user32.lib /OUT:NativeTestHost.exe
    if ($LASTEXITCODE) { throw 'Native fixture compilation failed' }
} finally { Pop-Location }
