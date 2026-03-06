@echo off

:: --- パス設定 ---
set NODE="C:\Program Files\nodejs\node.exe"
set APPJS="C:\App\webapp\app.js"

:: --- app.js のある場所に移動 ---
cd /d C:\App\webapp

:: --- Node.js アプリをバックグラウンドで起動 ---
start "" /MIN %NODE% %APPJS%
