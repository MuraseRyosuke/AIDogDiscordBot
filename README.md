# AI犬 - Discordチャットボット (ローカルLLM駆動)

「AI犬」は、ローカル環境で動作する大規模言語モデル (LLM) を活用した、個性豊かな犬型AIチャットボットです。Ollamaを通じて Gemma-2-2b-jpn-it (Q4_K_M量子化版) を使用し、Discordサーバーやダイレクトメッセージでユーザーとの対話を実現します。

!http://googleusercontent.com/image_generation_content/2
*(この画像は一例です。実際のボットのプロフィール画像に置き換えるか、この行を削除してください。)*

## 🌟 特徴

* 「AI犬」としての親しみやすいキャラクター性と言葉遣い。
* ローカルLLM (Gemma-2-2b-jpn-it Q4_K_M GGUF版) をOllama経由で利用するため、外部APIキーが不要。
* 会話履歴を記憶し、文脈に基づいた応答を試みます（直近数ターン）。
* Discordサーバーでのメンション、またはDMで気軽に対話可能。
* コマンドプレフィックス、レート制限、LLMパラメータなどを `.env` ファイルで設定可能。
* ボットの稼働状況を確認できる統計情報表示機能。
* ユーザーごとに会話履歴をリセットする機能。

## 🛠️ 技術スタック

* Python 3.10 以降
* nextcord (Discord APIラッパーライブラリ)
* Ollama (ローカルLLM実行環境)
* Gemma-2-2b-jpn-it (Q4_K_M GGUF版) (Google開発の日本語LLM)
* python-dotenv (環境変数管理)
* requests (Ollama API通信用)

## ⚙️ 動作環境

* Ollamaが動作するPC環境 (Windows 11推奨、macOS, Linuxでも動作可能)
* Python 3.10以降がインストールされた環境
* (推奨) 8GB以上のRAM (LLM実行のため)

## 🚀 セットアップ手順

1.  **リポジトリのクローン:**
    ```bash
    git clone [https://github.com/あなたのユーザー名/あなたのリポジトリ名.git](https://github.com/あなたのユーザー名/あなたのリポジトリ名.git)
    cd あなたのリポジトリ名
    ```

2.  **Python環境の準備:**
    * Python 3.10以降がインストールされていることを確認してください。
        ([Python公式サイト](https://www.python.org/)からダウンロードし、インストール時に「Add Python to PATH」にチェックを入れてください。)
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
    * (オプション) `PyNaCl`: ボイスチャット機能は使用しませんが、nextcordの警告を抑制したい場合はインストールしてください (`pip install PyNaCl`)。

3.  **OllamaとLLMモデルの準備:**
    * [Ollama公式サイト](https://ollama.com/) からお使いのOSに合ったOllamaをダウンロードし、インストールします。
    * 使用するLLMモデル `Gemma-2-2b-jpn-it (Q4_K_M GGUF版)` をOllamaに準備します。
        * **方法A (Ollama Hubから直接pullする場合 - 推奨):**
            Ollama Hubで `gemma-2-2b-jpn-it` を検索し、利用可能なタグから `q4_k_m` (または類似の量子化レベルを示すタグ) を見つけてpullします。
            ```bash
            ollama pull gemma-2-2b-jpn-it:q4_k_m
            ```
            *(注意: 上記のモデル名とタグはあくまで例です。Ollama Hubで実際に利用可能な正確な名前とタグを確認してください。コミュニティによって `ユーザー名/モデル名:タグ` の形式で提供されている場合もあります。)*
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
    * Ollamaサーバーが起動していることを確認してください (Ollama Desktopアプリを起動するか、ターミナルで `ollama serve` を実行)。

4.  **Discordボットの作成と設定:**
    * [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成します。
    * アプリケーションに「AI犬」などの名前を付けます。
    * 左メニューの「Bot」セクションでボットユーザーを作成し、必要であればユーザー名も「AI犬」に設定します。
    * 「TOKEN」セクションで「Reset Token」をクリックし、表示された**ボットトークン**をコピーします。これは次のステップで使用します。
    * 「Privileged Gateway Intents」セクションで「**MESSAGE CONTENT INTENT**」を必ず有効にしてください。

5.  **.env ファイルの作成と設定:**
    * プロジェクトのルートディレクトリ（`bot_main.py` と同じ場所）に `.env` という名前のファイルを作成します。
    * 以下の内容を `.env` ファイルに記述し、あなたの情報に置き換えてください。
        **注意: `BOT_TOKEN` は非常に機密性の高い情報です。この `.env` ファイルを絶対にGitHubなどの公開リポジトリにコミットしないでください。** (`.gitignore` ファイルで除外することを強く推奨します。)

        ```dotenv
        # 必須項目
        BOT_TOKEN="ここにあなたのDiscordボットトークンを貼り付け"
        OLLAMA_MODEL_NAME="gemma-2-2b-jpn-it:q4_k_m" # ステップ3でOllamaに準備したモデル名 (例: "ai-inu-gemma-q4km")
        OLLAMA_API_URL="http://localhost:11434/api/generate"

        # 任意項目 (設定しない場合はスクリプト内のデフォルト値が使用されます)
        ADMIN_USER_IDS="" # 管理者ユーザーのDiscord ID (複数いる場合はカンマ区切り。例: "123456789012345678,987654321098765432")
        BOT_COMMAND_PREFIX="!aidog " # ボットのコマンドプレフィックス (デフォルト: "!aidog ")

        OLLAMA_TEMPERATURE="0.7" # 応答の創造性 (0.0-1.0)
        OLLAMA_NUM_CTX="4096"    # モデルが考慮するコンテキストの最大長 (トークン数)
        OLLAMA_TOP_P="0.9"       # Top-pサンプリング
        OLLAMA_REPEAT_PENALTY="1.1" # 応答の繰り返し抑制

        MAX_CONVERSATION_HISTORY="5"  # ユーザーごとに記憶する最大会話往復数
        REQUEST_TIMEOUT="180"         # Ollama APIへのリクエストタイムアウト(秒)
        MAX_RESPONSE_LENGTH="1900"    # Discordに送信する最大応答文字数

        RATE_LIMIT_PER_USER="5"       # 1ユーザーあたりの最大リクエスト数
        RATE_LIMIT_WINDOW="60"        # 上記リクエスト数をカウントする期間 (秒)
        
        PROGRESS_UPDATE_INTERVAL="7"  # 「考え中」メッセージの更新間隔(秒)
        ```

6.  **(推奨) `.gitignore` ファイルの作成:**
    プロジェクトのルートディレクトリに `.gitignore` というファイルを作成し、以下のような内容を記述して、機密情報や不要なファイルがリポジトリに含まれないようにします。
    ```
    # Python
    __pycache__/
    *.py[cod]
    *$py.class
    venv/
    *.env
    .env

    # Log files
    *.log
    logs/

    # VSCode
    .vscode/
    ```

## ▶️ ボット「AI犬」の実行

1.  Ollamaサーバーが起動しており、モデルがロードできる状態であることを確認します。
    (Ollama Desktopアプリを起動するか、ターミナルで `ollama serve` を実行)
2.  プロジェクトのルートディレクトリで、ターミナルから以下のコマンドを実行してボットを起動します。
    ```bash
    python bot_main.py
    ```
    コンソールに「AI犬ボット「AI犬」(モデル: ...) が起動しましたワン！」といったメッセージが表示されれば成功です。

## 💬 「AI犬」の使い方

* **メンションで話しかける:** Discordサーバー内で `@AI犬 聞きたいこと` や `@AI犬 こんにちは！` のようにメンションして話しかけます。
* **DMで話しかける:** ボットにダイレクトメッセージを送ることで、1対1で対話できます。
* **コマンド:** (デフォルトのプレフィックスは `.env` で設定した `BOT_COMMAND_PREFIX`、初期値は `!aidog ` です)
    * `!aidog help`: ヘルプメッセージを表示します。
    * `!aidog stats`: ボットの稼働状況などの統計情報を表示します。
    * `!aidog clear`: あなたとAI犬との間の会話履歴をリセットします。
    * `!aidog reloadcfg`: (管理者のみ) `.env` から設定を再読み込みします（一部設定のみ）。

## ⚙️ 設定可能な項目

`.env` ファイルを通じて、以下の主要な項目を設定・調整できます。詳細はセットアップ手順5の `.env` ファイルの例を参照してください。

* Discordボットトークン (`BOT_TOKEN`)
* Ollamaで使用するモデル名 (`OLLAMA_MODEL_NAME`) とAPI URL (`OLLAMA_API_URL`)
* 管理者ユーザーID (`ADMIN_USER_IDS`)
* コマンドプレフィックス (`BOT_COMMAND_PREFIX`)
* LLMの生成パラメータ (`OLLAMA_TEMPERATURE`, `OLLAMA_NUM_CTX`, `OLLAMA_TOP_P`, `OLLAMA_REPEAT_PENALTY`)
* 会話履歴の管理 (`MAX_CONVERSATION_HISTORY`)
* APIリクエストのタイムアウト (`REQUEST_TIMEOUT`)
* Discordへの最大応答文字数 (`MAX_RESPONSE_LENGTH`)
* ユーザーごとのレート制限 (`RATE_LIMIT_PER_USER`, `RATE_LIMIT_WINDOW`)
* 「考え中」メッセージの更新間隔 (`PROGRESS_UPDATE_INTERVAL`)

## 📝 注意事項

* このボットはローカルPC上で動作するため、ボットを実行しているPCが起動していないとDiscord上ではオフラインになります。常時稼働させたい場合は、PCを常時起動しておくか、別途サーバー環境を検討する必要があります。
* ローカルPCのスペック（特にCPUとRAM）によっては、LLMの応答に時間がかかることがあります。Gemma-2-2b-jpn-it Q4_K_M は比較的軽量ですが、それでも8GB RAMの環境ではメモリ管理に注意し、他の重いアプリケーションとの同時実行は避けるのが賢明です。
* PC起動時にボット（OllamaサーバーとPythonスクリプト）を自動起動するように設定すると便利です（手順はOSによって異なります）。

---

このAI犬ボットが、あなたのDiscord生活に新しい楽しみをもたらすことを願っています！
