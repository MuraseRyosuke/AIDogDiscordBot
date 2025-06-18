@echo off
rem --- このバッチファイルは、AI犬BotをWindows環境で起動します。---

rem ウィンドウのタイトルを設定
title AI-Dog Bot Launcher

echo -------------------------------------
echo  AI-Dog Discord Bot Launcher
echo -------------------------------------
echo.

rem --- スクリプトのあるディレクトリへ移動 ---
rem これにより、どこから実行してもパスの問題が起きなくなります。
cd /d "%~dp0"
echo [INFO] 作業ディレクトリ: %CD%
echo.

rem --- 仮想環境(venv)の有効化を試みる ---
echo [INFO] 仮想環境 (venv) を探しています...
if exist "venv\Scripts\activate.bat" (
    echo [OK] 仮想環境を有効化します...
    call "venv\Scripts\activate.bat"
    echo.
) else (
    echo [WARN] 仮想環境が見つかりませんでした。グローバルのPythonで実行します。
    echo         ライブラリ関連のエラーが出る場合は、コマンドプロンプトで
    echo         pip install -r requirements.txt を実行してください。
    echo.
)

rem --- Pythonスクリプトを実行 ---
echo [INFO] AI犬Bot (bot_main.py) を起動します...
echo        (Botを停止するには、このウィンドウで Ctrl+C を押してください)
echo -------------------------------------
echo.

python bot_main.py

echo.
echo -------------------------------------
echo [INFO] ボットのプロセスが終了しました。
echo.
echo コンソールウィンドウにエラーメッセージが表示されていないか確認してください。
echo 何かキーを押すとこのウィンドウは閉じます...
pause