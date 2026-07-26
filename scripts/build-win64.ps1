[CmdletBinding()]
param(
    [string]$PythonExe
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ExpectedPython = "3.11.9"
$ExpectedUnrarPackageHash = "CA630E4D4EFF213076DEF6690CC82EAD81ABB739158DA7EAD3FD263FF9D104E5"
$ExpectedUnrarExeHash = "0D3715001790F0FD18D3E850F947B540530B2D2DEB9A2E6A9E84F2ED7B234235"
$UnrarUrl = "https://www.rarlab.com/rar/unrarw64.exe"

function Assert-PathInsideProject {
    param([Parameter(Mandatory)][string]$Path)

    $projectFullPath = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $targetFullPath = [IO.Path]::GetFullPath($Path)
    if (-not $targetFullPath.StartsWith(
        $projectFullPath + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to operate outside the project: $targetFullPath"
    }
}

function Get-PeMachine {
    param([Parameter(Mandatory)][string]$Path)

    $stream = [IO.File]::OpenRead($Path)
    try {
        $reader = New-Object IO.BinaryReader($stream)
        if ($reader.ReadUInt16() -ne 0x5A4D) {
            throw "Not a PE file: $Path"
        }
        $stream.Position = 0x3C
        $peOffset = $reader.ReadInt32()
        $stream.Position = $peOffset
        if ($reader.ReadUInt32() -ne 0x00004550) {
            throw "Invalid PE signature: $Path"
        }
        return $reader.ReadUInt16()
    }
    finally {
        $stream.Dispose()
    }
}

Set-Location $ProjectRoot

if (-not $PythonExe) {
    $localPython = Join-Path $ProjectRoot ".python-build\3.11.9\python.exe"
    if (Test-Path -LiteralPath $localPython) {
        $PythonExe = $localPython
    }
    elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $PythonExe = (& py.exe -3.11 -c "import sys; print(sys.executable)").Trim()
    }
}

if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python 3.11.9 x64 was not found. Install it or pass -PythonExe <path>."
}

$pythonInfo = & $PythonExe -c "import json,platform,sys; print(json.dumps({'version': platform.python_version(), 'bits': platform.architecture()[0], 'implementation': platform.python_implementation(), 'executable': sys.executable}))"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect Python: $PythonExe"
}
$python = $pythonInfo | ConvertFrom-Json
if ($python.version -ne $ExpectedPython -or $python.bits -ne "64bit" -or $python.implementation -ne "CPython") {
    throw "Expected CPython $ExpectedPython x64; found $($python.implementation) $($python.version) $($python.bits)."
}

$venvPath = Join-Path $ProjectRoot ".venv-build"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
Assert-PathInsideProject $venvPath
if (Test-Path -LiteralPath $venvPath) {
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}
& $PythonExe -m venv $venvPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the build virtual environment."
}

& $venvPython -m pip install --require-hashes --requirement (Join-Path $ProjectRoot "requirements-win64.lock")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install locked build dependencies."
}

$unrarRoot = Join-Path $ProjectRoot ".build-cache\unrar"
$unrarPackage = Join-Path $unrarRoot "unrarw64.exe"
$unrarExtracted = Join-Path $unrarRoot "extracted"
$unrarExe = Join-Path $unrarExtracted "UnRAR.exe"
New-Item -ItemType Directory -Force -Path $unrarRoot | Out-Null

if (-not (Test-Path -LiteralPath $unrarPackage)) {
    Invoke-WebRequest -Uri $UnrarUrl -OutFile $unrarPackage
}
$packageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $unrarPackage).Hash
if ($packageHash -ne $ExpectedUnrarPackageHash) {
    throw "Official UnRAR package checksum mismatch. Expected $ExpectedUnrarPackageHash; found $packageHash."
}

$unrarIsValid = (Test-Path -LiteralPath $unrarExe) -and (
    (Get-FileHash -Algorithm SHA256 -LiteralPath $unrarExe).Hash -eq $ExpectedUnrarExeHash
)
if (-not $unrarIsValid) {
    Assert-PathInsideProject $unrarExtracted
    if (Test-Path -LiteralPath $unrarExtracted) {
        Remove-Item -LiteralPath $unrarExtracted -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $unrarExtracted | Out-Null
    $extractArgument = "-d`"$unrarExtracted`""
    $extractProcess = Start-Process -FilePath $unrarPackage `
        -ArgumentList @("-s", $extractArgument) `
        -Wait -PassThru -WindowStyle Hidden
    if ($extractProcess.ExitCode -ne 0) {
        throw "UnRAR package extraction failed with exit code $($extractProcess.ExitCode)."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $unrarExtracted "license.txt"))) {
    throw "UnRAR license was not extracted."
}
$unrarHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $unrarExe).Hash
if ($unrarHash -ne $ExpectedUnrarExeHash -or (Get-PeMachine $unrarExe) -ne 0x8664) {
    throw "The staged UnRAR executable is not the pinned x64 build."
}

$distPath = Join-Path $ProjectRoot "dist\HappyPanda"
Assert-PathInsideProject $distPath
if (Test-Path -LiteralPath $distPath) {
    Remove-Item -LiteralPath $distPath -Recurse -Force
}

& $venvPython (Join-Path $ProjectRoot "freeze.py") build_exe
if ($LASTEXITCODE -ne 0) {
    throw "cx_Freeze failed."
}

$exePath = Join-Path $distPath "Happypanda.exe"
if ((Get-PeMachine $exePath) -ne 0x8664) {
    throw "Happypanda.exe is not an AMD64 executable."
}

$nativeFiles = Get-ChildItem -LiteralPath $distPath -Recurse -File |
    Where-Object {
        $_.Extension -in @(".exe", ".pyd") -or
        $_.Name -eq "python311.dll" -or
        $_.Name -like "Qt5*.dll"
    }
$wrongArchitecture = @(
    foreach ($file in $nativeFiles) {
        if ((Get-PeMachine $file.FullName) -ne 0x8664) {
            $file.FullName
        }
    }
)
if ($wrongArchitecture.Count -gt 0) {
    throw "Non-AMD64 binaries were found:`n$($wrongArchitecture -join [Environment]::NewLine)"
}

$versionProcess = Start-Process -FilePath $exePath -ArgumentList "--version" -Wait -PassThru -WindowStyle Hidden
if ($versionProcess.ExitCode -ne 0) {
    throw "Frozen executable smoke test failed with exit code $($versionProcess.ExitCode)."
}
$unexpectedRuntimeData = @(
    @(
        "settings.ini",
        ".happypanda",
        "db",
        "downloads",
        "temp",
        "happypanda.log"
    ) | ForEach-Object { Join-Path $distPath $_ } | Where-Object {
        Test-Path -LiteralPath $_
    }
)
if ($unexpectedRuntimeData.Count -gt 0) {
    throw "Build smoke test created user data:`n$($unexpectedRuntimeData -join [Environment]::NewLine)"
}

$gitCommit = (& git rev-parse HEAD).Trim()
$gitDirty = [bool](& git status --porcelain)
$cxFreezeVersion = & $venvPython -c "import cx_Freeze; print(cx_Freeze.__version__)"
$buildInfo = [ordered]@{
    application = "HappyPanda"
    application_version = "1.2"
    architecture = "AMD64"
    build_time_utc = [DateTime]::UtcNow.ToString("o")
    cx_freeze = $cxFreezeVersion.Trim()
    git_commit = $gitCommit
    git_dirty = $gitDirty
    python = $ExpectedPython
    unrar = "7.23 x64"
    unrar_sha256 = $ExpectedUnrarExeHash
}
$buildInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $distPath "BUILD-INFO.json") -Encoding UTF8

$checksumPath = Join-Path $distPath "SHA256SUMS.txt"
Get-ChildItem -LiteralPath $distPath -Recurse -File |
    Where-Object { $_.FullName -ne $checksumPath } |
    Sort-Object FullName |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($distPath.Length).TrimStart("\").Replace("\", "/")
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        "$hash  $relativePath"
    } | Set-Content -LiteralPath $checksumPath -Encoding ASCII

Write-Host "HappyPanda Windows x64 build completed:"
Write-Host "  $distPath"
