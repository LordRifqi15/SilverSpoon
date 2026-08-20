@echo off
echo Building SilverSpoon distribution with bundled Playwright Chromium...
echo This can take several minutes and produces a large folder.
echo.

pyinstaller --clean --noconsole --onedir --icon="SilverSpoon.ico" --add-binary "7z.exe;." --add-binary "7z.dll;." --add-data "SilverSpoon.ico;." --add-data "SilverSpoon.png;." --copy-metadata "curl_cffi" --name "SilverSpoon" pyqt_downloader.py
if errorlevel 1 goto :error

powershell -NoProfile -Command "$source = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'ms-playwright') -Directory -Filter 'chromium-*' | Where-Object { $_.Name -notlike 'chromium_headless*' } | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'chrome-win64' } | Where-Object { Test-Path (Join-Path $_ 'chrome.exe') } | Select-Object -First 1; if (-not $source) { Write-Error 'Playwright Chromium was not found under %LOCALAPPDATA%\ms-playwright.'; exit 1 }; Copy-Item -LiteralPath $source -Destination 'dist\SilverSpoon\playwright-chromium' -Recurse -Force"
if errorlevel 1 goto :error

echo.
echo Build complete! Distribute the entire 'dist\SilverSpoon' folder.
pause
exit /b 0

:error
echo.
echo Build failed.
pause
exit /b 1
