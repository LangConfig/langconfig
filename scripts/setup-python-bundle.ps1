# LangConfig - Python Bundle Setup Script (Windows)
# Downloads and configures python-build-standalone for bundling

$ErrorActionPreference = "Stop"

Write-Host "🐍 Setting up Python standalone for LangConfig..." -ForegroundColor Cyan

# Python version configuration
$PythonVersion = "3.12.7"
$BuildDate = "20241016"
$PythonBuild = "cpython-$PythonVersion+$BuildDate-x86_64-pc-windows-msvc-shared-install_only.tar.gz"
$DownloadUrl = "https://github.com/indygreg/python-build-standalone/releases/download/$BuildDate/$PythonBuild"

# Directories
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PythonDir = Join-Path $ProjectRoot "src-tauri\python"
$BackendDir = Join-Path $ProjectRoot "backend"
$BackendLib = Join-Path $BackendDir "lib"

Write-Host "📁 Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackendLib | Out-Null

# Download Python standalone
Write-Host "⬇️  Downloading Python standalone: $PythonBuild" -ForegroundColor Yellow
$DownloadPath = Join-Path $ProjectRoot $PythonBuild

if (Test-Path $DownloadPath) {
    Write-Host "✓ Python build already downloaded" -ForegroundColor Green
} else {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $DownloadPath
    Write-Host "✓ Download complete" -ForegroundColor Green
}

# Extract Python (requires tar on Windows 10+, or 7-Zip)
Write-Host "📦 Extracting Python standalone..." -ForegroundColor Yellow

if (Get-Command tar -ErrorAction SilentlyContinue) {
    tar -xzf $DownloadPath -C $PythonDir --strip-components=1
} elseif (Get-Command 7z -ErrorAction SilentlyContinue) {
    7z x $DownloadPath -so | 7z x -si -ttar -o"$PythonDir"
} else {
    Write-Host "❌ Neither tar nor 7-Zip found. Please install one to extract the archive." -ForegroundColor Red
    exit 1
}

Write-Host "✓ Python extracted to: $PythonDir" -ForegroundColor Green

# Python executable path
$PythonExe = Join-Path $PythonDir "python.exe"

# Verify Python installation
Write-Host "🔍 Verifying Python installation..." -ForegroundColor Yellow
& $PythonExe --version

# Install backend dependencies
Write-Host "📚 Installing backend dependencies..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt") -t $BackendLib
Write-Host "✓ Dependencies installed to: $BackendLib" -ForegroundColor Green

# Cleanup
Write-Host "🧹 Cleaning up..." -ForegroundColor Yellow
Remove-Item $DownloadPath

Write-Host ""
Write-Host "✅ Python standalone setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Python location: $PythonDir"
Write-Host "Python executable: $PythonExe"
Write-Host "Backend libraries: $BackendLib"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Run 'npm run tauri dev' to test in development mode"
Write-Host "  2. Run 'npm run tauri build' to create production bundle"
Write-Host ""
