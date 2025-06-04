@echo off
echo AI犬ボットを起動します...

REM ↓↓↓ この下の行のパスを、あなたの実際のプロジェクトフォルダのパスに書き換えてください ↓↓↓
cd C:\AIDogDiscordBot 

echo 現在のディレクトリ: %CD%
echo Pythonスクリプトを実行します: python bot_main.py

python bot_main.py

echo.
echo AI犬ボットの処理が終了しました。
echo 何か問題が発生した場合は、このウィンドウにエラーメッセージが表示されている可能性があります。
pause