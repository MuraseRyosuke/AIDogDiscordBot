# AI犬 - Discordチャットボット (ローカルLLM駆動)

「AI犬」は、ローカル環境で動作する大規模言語モデル (LLM) を活用した、個性豊かな犬型AIチャットボットです。Ollamaを通じて Gemma-2-2b-jpn-it (Q4_K_M量子化版) を使用し、Discordサーバーやダイレクトメッセージでユーザーとの対話を実現します。天気情報を取得したり、ユーザーからのファイル添付に反応したりする機能も備えています。

![Image](https://github.com/user-attachments/assets/1d399488-3c07-4460-b7a0-49b74ae4f6ba)

## 🌟 特徴

* 「AI犬」としての親しみやすいキャラクター性と言葉遣い。
* ローカルLLM (Gemma-2-2b-jpn-it Q4_K_M GGUF版) をOllama経由で利用するため、外部APIキーが不要（天気機能を除く）。
* 会話履歴をSQLiteデータベースに永続化し、再起動後も文脈をある程度引き継ぎます。
* Discordサーバーでのメンション、またはDMで気軽に対話可能。
* ユーザーからのファイル添付（テキストファイル、画像）に反応し、テキストファイルの内容は対話に利用可能。
* 指定した都市の現在の天気情報を表示（OpenWeatherMap APIを利用）。
* 設定可能なコマンドプレフィックス、レート制限、LLMパラメータなど。
* ボットの稼働状況を確認できる統計情報表示機能。
* ユーザーごとに会話履歴をリセットする機能。
* ボットからサンプル画像やテキストファイルを送信するサンプルコマンド。

## 🛠️ 技術スタック

* Python 3.10 以降
* nextcord (Discord APIラッパーライブラリ)
* Ollama (ローカルLLM実行環境)
* Gemma-2-2b-jpn-it (Q4_K_M GGUF版) (Google開発の日本語LLM)
* python-dotenv (環境変数管理)
* requests (Ollama APIおよび天気API通信用)
* sqlite3 (会話ログ永続化用、Python標準ライブラリ)

## ⚙️ 動作環境

* Ollamaが動作するPC環境 (Windows 11推奨、macOS, Linuxでも動作可能)
* Python 3.10以降がインストールされた環境
* (推奨) 8GB以上のRAM (LLM実行のため)
* (天気機能利用時) OpenWeatherMapのAPIキー

## 🚀 セットアップ手順

1.  **リポジトリのクローン (またはファイルのダウンロード):**
    ```bash
    git clone [https://github.com/MuraseRyosuke/AIDogDiscordBot.git](https://github.com/MuraseRyosuke/AIDogDiscordBot.git)
    cd AIDogDiscordBot
    ```
    *(リポジトリを公開していない場合は、`bot_main.py` などのファイルをPC上の任意のフォルダに保存してください。)*

2.  **Python環境の準備:**
    * Python 3.10以降がインストールされていることを確認してください。
        * [Python公式サイト](https://www.python.org/)からダウンロードし、インストール時に**「Add Python to PATH」に必ずチェックを入れてください。**
    * (推奨) 仮想環境を作成して有効化します。
        ```bash
        python -m venv venv
        # Windowsの場合
        .\venv\Scripts\activate
        # macOS/Linuxの場合
        # source venv/bin/activate
        ```
    * 必要なライブラリをインストールします。プロジェクトルートに以下の内容で `requirements.txt` を作成してください。
        ```txt
        nextcord
        python-dotenv
        requests
        ```
        その後、ターミナルで以下を実行します:
        ```bash
        pip install -r requirements.txt
        ```
    * (オプション) `PyNaCl`: ボイスチャット機能は使用しませんが、nextcordが出す「PyNaCl is not installed」という警告を抑制したい場合はインストールしてください (`pip install PyNaCl`)。

3.  **OllamaとLLMモデルの準備:**
    * [Ollama公式サイト](https://ollama.com/) からお使いのOSに合ったOllamaをダウンロードし、インストールします。
    * 使用するLLMモデル `Gemma-2-2b-jpn-it (Q4_K_M GGUF版)` をOllamaに準備します。
        * **方法A (Ollama Hubから直接pullする場合 - 推奨):**
            Ollama Hubで `gemma-2-2b-jpn-it` を検索し、利用可能なタグから `q4_k_m` (または類似の量子化レベルを示すタグ、例: `Q4_K_M`) を見つけてpullします。
            ```bash
            ollama pull schroneko/gemma-2-2b-jpn-it:q4_K_M
            ```
            *(注意: 上記のモデル名とタグはあくまで例です。Ollama Hubで実際に利用可能な正確な名前とタグを確認してください。)*
            この方法で入手した場合、`.env` ファイルの `OLLAMA_MODEL_NAME` にはこのフルネームを指定します。
        * **方法B (GGUFファイルを手動でダウンロードしてOllamaにカスタムモデルとして登録する場合):**
            1.  `gemma-2-2b-jpn-it.Q4_K_M.gguf` ファイル (ファイルサイズ約1.71GB) をHugging Faceの `bartowski/gemma-2-2b-jpn-it-GGUF` リポジトリなどからダウンロードします。
            2.  ダウンロードしたGGUFファイルをPCの任意のフォルダ (例: `C:\OllamaModels`) に保存します。
            3.  プロジェクトルートに以下の内容で `Modelfile` (拡張子なし) を作成します。`FROM` のパスは実際のGGUFファイルの保存場所に合わせてください。
                ```modelfile
                FROM C:/OllamaModels/gemma-2-2b-jpn-it.Q4_K_M.gguf
                PARAMETER num_ctx 4096 
                # 必要に応じて他のPARAMETERやTEMPLATEをモデルの推奨に合わせて設定
                ```
            4.  ターミナルで `Modelfile` があるディレクトリに移動し、Ollamaにモデルを登録します (例: `ai-inu-gemma-q4km` という名前で登録する場合)。
                ```bash
                ollama create ai-inu-gemma-q4km -f Modelfile
                ```
            この方法で登録した場合、`.env` ファイルの `OLLAMA_MODEL_NAME` にはここで付けた名前 (例: `ai-inu-gemma-q4km`) を指定します。
    * Ollamaサーバーが起動していることを確認してください (Ollama Desktopアプリを起動するか、ターミナルで `ollama serve` を実行)。

4.  **Discordボットの作成と設定:**
    * [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成します。
    * アプリケーションに「AI犬」などの名前を付けます。
    * 左メニューの「Bot」セクションでボットユーザーを作成し、必要であればユーザー名も「AI犬」に設定します。ここで表示されるボットのプロフィール画像も設定できます。
    * 「TOKEN」セクションで「Reset Token」をクリックし、表示された**ボットトークン**をコピーします。
    * 「Privileged Gateway Intents」セクションで「**MESSAGE CONTENT INTENT**」を必ず有効にしてください。

5.  **.env ファイルの作成と設定:**
    * プロジェクトのルートディレクトリ（`bot_main.py` と同じ場所）に `.env` という名前のファイルを作成します。
    * 以下の内容を `.env` ファイルに記述し、あなたの情報に置き換えてください。
        **注意: `BOT_TOKEN` と `OPENWEATHERMAP_API_KEY` は機密情報です。この `.env` ファイルを絶対にGitHubなどの公開リポジトリにコミットしないでください。** (`.gitignore` ファイルで除外することを強く推奨します。)

        ```dotenv
        # 必須項目
        BOT_TOKEN="ここにあなたのDiscordボットトークンを貼り付け"
        OLLAMA_MODEL_NAME="schroneko/gemma-2-2b-jpn-it:q4_K_M" # ステップ3でOllamaに準備したモデル名
        OLLAMA_API_URL="http://localhost:11434/api/generate"

        # 天気機能を利用する場合に必須 (OpenWeatherMapから取得)
        OPENWEATHERMAP_API_KEY="" # ここにあなたのOpenWeatherMapのAPIキー

        # 任意項目 (設定しない場合はスクリプト内のデフォルト値が使用されます)
        ADMIN_USER_IDS="" # 管理者ユーザーのDiscord ID (カンマ区切り)
        BOT_COMMAND_PREFIX="!aidog "
        
        OLLAMA_TEMPERATURE="0.7"
        OLLAMA_NUM_CTX="4096"
        OLLAMA_TOP_P="0.9"
        OLLAMA_REPEAT_PENALTY="1.1"
        
        MAX_CONVERSATION_HISTORY="5"
        REQUEST_TIMEOUT="180"
        MAX_RESPONSE_LENGTH="1900"
        
        RATE_LIMIT_PER_USER="5"
        RATE_LIMIT_WINDOW="60"
        
        WEATHER_DEFAULT_CITY="東京"
        CONVERSATION_DB_PATH="ai_dog_conversation_history.sqlite3"
        PROGRESS_UPDATE_INTERVAL="7"
        ```

6.  **(推奨) `.gitignore` ファイルの作成:**
    プロジェクトのルートディレクトリに `.gitignore` というファイルを作成し、以下のような内容を記述します。
    ```
    # Python
    __pycache__/
    *.py[cod]
    *$py.class
    venv/
    *.venv/
    env/
    ENV/

    # Environment variables
    .env
    *.env.*

    # Log files and databases
    *.log
    logs/
    *.sqlite3
    *.db
    ai_dog_conversation_history.sqlite3 # 明示的に指定

    # VSCode
    .vscode/

    # Ollama Models (もしプロジェクト内にダウンロードする場合)
    # OllamaModels/ 
    ```

## ▶️ ボット「AI犬」の実行

1.  **Ollamaサーバーを起動します。**
    * Ollama Desktopアプリケーションを起動するか、ターミナルで `ollama serve` コマンドを実行します。
    * （エラーが出る場合: `listen tcp 127.0.0.1:11434: bind: Only one usage of each socket address...` というエラーは、Ollamaが既に別の場所で起動している（例: Desktopアプリと`ollama serve`コマンドの二重起動）ことを意味します。どちらか一方だけ実行してください。）
2.  プロジェクトのルートディレクトリで、ターミナルから以下のコマンドを実行してボットを起動します。
    ```bash
    python bot_main.py
    ```
    コンソールに「AI犬ボット「AI犬」(モデル: ...) が起動しましたワン！」といったメッセージが表示されれば成功です。
    （エラーが出る場合: `404 Client Error: Not Found for url: http://localhost:11434/api/generate` はOllamaサーバーが正しく起動していないか、API URLが間違っている可能性があります。）

## 💬 「AI犬」の使い方

* **メンションで話しかける:** Discordサーバー内で `@AI犬 聞きたいこと` や `@AI犬 こんにちは！` のようにメンションして話しかけます。メッセージにファイルを添付することもできます。
* **DMで話しかける:** ボットにダイレクトメッセージを送ることで、1対1で対話できます。
* **コマンド:** (デフォルトのプレフィックスは `.env` で設定した `BOT_COMMAND_PREFIX`、初期値は `!aidog ` です)
    * `!aidog help`: ヘルプメッセージを表示します。
    * `!aidog stats`: ボットの稼働状況などの統計情報を表示します。
    * `!aidog clear`: あなたとAI犬との間の会話履歴をリセットします。
    * `!aidog weather <都市名>`: 指定した都市の現在の天気情報を表示します（都市名省略時はデフォルト都市）。
    * `!aidog bone`: AI犬からホネのサンプル画像を送信します（`bot_images/bone.png` が必要）。
    * `!aidog textfile`: AI犬からサンプルテキストファイルを送信します。
    * `!aidog reloadcfg`: (管理者のみ) `.env` から設定を再読み込みします（一部設定のみ）。

## ⚙️ 設定可能な項目

`.env` ファイルを通じて以下の主要な項目を設定・調整できます。詳細はセットアップ手順5の `.env` ファイルの例を参照してください。

* Discordボットトークン (`BOT_TOKEN`)
* Ollamaで使用するモデル名 (`OLLAMA_MODEL_NAME`) とAPI URL (`OLLAMA_API_URL`)
* OpenWeatherMap APIキー (`OPENWEATHERMAP_API_KEY`)
* 管理者ユーザーID (`ADMIN_USER_IDS`)
* コマンドプレフィックス (`BOT_COMMAND_PREFIX`)
* LLMの生成パラメータ (temperature, num_ctx, top_p, repeat_penalty)
* 会話履歴の管理 (保持数 `MAX_CONVERSATION_HISTORY`, DBパス `CONVERSATION_DB_PATH`)
* APIリクエストのタイムアウト (`REQUEST_TIMEOUT`)
* Discordへの最大応答文字数 (`MAX_RESPONSE_LENGTH`)
* ユーザーごとのレート制限 (`RATE_LIMIT_PER_USER`, `RATE_LIMIT_WINDOW`)
* 天気機能のデフォルト都市 (`WEATHER_DEFAULT_CITY`)
* 「考え中」メッセージの更新間隔 (`PROGRESS_UPDATE_INTERVAL`)

## 📝 注意事項

* このボットはローカルPC上で動作するため、ボットを実行しているPCが起動していないとDiscord上ではオフラインになります。
* ローカルPCのスペック（特にCPUとRAM）によっては、LLMの応答に時間がかかることがあります。Gemma-2-2b-jpn-it Q4_K_M は比較的軽量ですが、8GB RAMの環境ではメモリ管理に注意し、他の重いアプリケーションとの同時実行は避けるのが賢明です。
* PC起動時にボット（OllamaサーバーとPythonスクリプト）を自動起動するように設定すると便利です。

## 💡 トラブルシューティングのヒント

* **「Ollama APIに接続できない」「404 Not Found」等のエラー:**
    * Ollamaサーバー (Ollama Desktopアプリまたは `ollama serve` コマンド) が正しく起動しているか確認してください。
    * `.env` ファイルの `OLLAMA_API_URL` が正しいか (`http://localhost:11434/api/generate`) 確認してください。
    * ファイアウォールがローカル通信をブロックしていないか確認してください。
* **`.bat` ファイル実行時に「このアプリはお使いのPCでは実行できません」または「python コマンドが見つかりません」等のエラー:**
    * Pythonが正しくインストールされ、インストール時に「Add Python to PATH」にチェックを入れたか確認してください。コマンドプロンプトで `python --version` が動作するか試してください。
    * `.bat` ファイル内の `cd C:\path\to\your\project` のパスが、`bot_main.py` のある実際のフォルダパスと一致しているか確認してください。
* **ボット起動時の「ADMIN_USER_IDS の形式が不正です」警告:**
    * `.env` ファイルの `ADMIN_USER_IDS` の値が、カンマ区切りの数値の羅列になっているか確認してください (例: `ADMIN_USER_IDS="123,456"`)。管理者を設定しない場合は空欄 `ADMIN_USER_IDS=""` にするか、行自体を削除します。
* **ボットがDiscordに接続できない、またはエラーで落ちる:**
    * `.env` ファイルの `BOT_TOKEN` が正しいか確認してください。
    * Discord Developer Portalでボットの「MESSAGE CONTENT INTENT」が有効になっているか確認してください。
    * コンソールやログファイル (`ai_dog_bot.log`) に出力されるエラーメッセージを確認してください。

---

このAI犬ボットが、あなたのDiscord生活に新しい楽しみをもたらすことを願っています！
