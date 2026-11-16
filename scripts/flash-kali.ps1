[CmdletBinding()]
param(
    [string]$ImageDirectory = (Join-Path $PSScriptRoot '..\out'),
    [string]$Serial,
    [string]$FastbootPath = 'fastboot',
    [switch]$EraseUserdata
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if (-not $EraseUserdata) {
    throw 'This installs Kali on userdata and erases all Android user data. Pass -EraseUserdata only when that is intended.'
}
$ImageDirectory = (Resolve-Path -LiteralPath $ImageDirectory).Path
& python (Join-Path $PSScriptRoot 'validate-images.py') $ImageDirectory
if ($LASTEXITCODE -ne 0) { throw 'Image validation failed; nothing was flashed.' }
$manifest = Get-Content -LiteralPath (Join-Path $ImageDirectory 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.device -ne 'sheng' -or $manifest.architecture -ne 'arm64' -or $manifest.desktop -ne 'kde' -or
    $manifest.distribution -ne 'kali' -or $manifest.root_partition -ne 'userdata' -or
    $manifest.host_image_validation -ne 'passed') {
    throw 'The image is not Kali ARM64 KDE for sheng.'
}
function Invoke-Fastboot {
    param([string[]]$Arguments)
    & $script:FastbootPath -s $script:Serial @Arguments 2>&1 | ForEach-Object {
        Write-Host $_
        Add-Content -LiteralPath (Join-Path $script:ImageDirectory 'flash-log.txt') -Value $_.ToString() -Encoding utf8
    }
    if ($LASTEXITCODE -ne 0) { throw ('fastboot failed: ' + ($Arguments -join ' ')) }
}
function Get-FastbootVariable {
    param([string]$Name)
    $result = (& $script:FastbootPath -s $script:Serial getvar $Name 2>&1 | ForEach-Object { $_.ToString() }) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $result -notmatch ('(?m)^' + [regex]::Escape($Name) + ':\s*(\S+)')) {
        throw "Unable to verify fastboot variable: $Name ($result)"
    }
    return $Matches[1]
}
$devices = @(& $FastbootPath devices | ForEach-Object { if ($_ -match '^(\S+)\s+fastboot') { $Matches[1] } })
if (-not $Serial) {
    if ($devices.Count -ne 1) { throw 'Connect exactly one device in fastboot mode, or specify -Serial.' }
    $Serial = $devices[0]
}
if ($Serial -notin $devices) { throw 'Selected device is not connected in fastboot mode.' }
if ((Get-FastbootVariable 'product') -ne 'sheng') { throw 'Wrong tablet model; nothing was flashed.' }
if ((Get-FastbootVariable 'unlocked') -ne 'yes') { throw 'Bootloader is locked; nothing was flashed.' }
$userdataBytes = [Convert]::ToInt64((Get-FastbootVariable 'partition-size:userdata').Replace('0x',''),16)
$bootBytes = [Convert]::ToInt64((Get-FastbootVariable 'partition-size:boot_b').Replace('0x',''),16)
if ($userdataBytes -lt $manifest.expanded_rootfs_bytes) { throw 'Rootfs is larger than the userdata partition.' }
if ($bootBytes -lt (Get-Item -LiteralPath (Join-Path $ImageDirectory 'boot-kali-sheng.img')).Length) {
    throw 'Kernel image is larger than boot_b.'
}
$record = [ordered]@{
    serial = $Serial
    product = 'sheng'
    previous_slot = (Get-FastbootVariable 'current-slot')
    userdata_bytes = $userdataBytes
    started_at = (Get-Date).ToString('o')
    completed = $false
    device_boot_verified = $false
}
$recordPath = Join-Path $ImageDirectory 'flash-record.json'
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
Write-Host 'Installing native Kali ARM64 KDE. All Android user data on userdata will be erased.'
# Leave slot A boot/dtbo and both recovery partitions intact for recovery.
# Install rootfs first so a failed transfer does not replace the active kernel.
Invoke-Fastboot -Arguments @('-S', '256M', 'flash', 'userdata', (Join-Path $ImageDirectory 'rootfs-kali-arm64-kde-sheng.img'))
Invoke-Fastboot -Arguments @('flash', 'boot_b', (Join-Path $ImageDirectory 'boot-kali-sheng.img'))
Invoke-Fastboot -Arguments @('erase', 'dtbo_b')
Invoke-Fastboot -Arguments @('set_active', 'b')
Invoke-Fastboot -Arguments @('reboot')
$record.completed = $true
$record.finished_at = (Get-Date).ToString('o')
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
Write-Host 'Images written. Boot and KDE desktop still need to be verified on the tablet.'
