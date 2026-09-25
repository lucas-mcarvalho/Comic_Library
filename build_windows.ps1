$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$dlls = @("archive.dll","charset.dll","iconv.dll","libbz2.dll","liblzma.dll","libxml2.dll","libzstd.dll","lz4.dll","zlib.dll","zstd.dll")
$addBin = $dlls | ForEach-Object { "--add-binary", "app\$_;." }

& .\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --name "ComicLibrary" @addBin run.py

Write-Output "Executavel gerado em dist\ComicLibrary.exe"
