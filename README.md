# AI犬 - ローカルLLM駆動型 Discordチャットボット

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Nextcord](https://img.shields.io/badge/Nextcord-2.6.0-7289DA?style=for-the-badge&logo=discord&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-lightgrey?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**AI犬 (AI-Dog)** は、[Ollama](https://ollama.com/) を利用してローカル環境で大規模言語モデル（LLM）を動かし、Discord上で対話するための多機能チャットボットプロジェクトです。

単なるチャット機能だけでなく、個別の会話履歴管理、豊富なコマンド、柔軟な設定機能などを備えた、実践的なボット開発のテンプレートとしても利用できます。

![Image](https://github.com/user-attachments/assets/6b515254-db40-4250-932d-096bb52bebb2)

## 主な機能

* 🧠 **ローカルLLM連携 (Ollama):** お手元のPCで動作する好きな言語モデルをAIの頭脳として利用できます。APIキーは不要です。
* 🐾 **個性的な「AI犬」ペルソナ:** 高度な分析能力とご主人様への忠誠心を併せ持つ、ユニークなAI犬としての応答を生成します。プロンプトエンジニアリングの実践例としても参考になります。
* 📚 **会話履歴の永続化 (SQLite):** ユーザーごとに会話の文脈を記憶し、過去のやり取りを踏まえた自然な対話を実現します。
* ⚙️ **柔軟な設定:** ボットトークンやモデル名、各種パラメータを`.env`ファイルで安全かつ簡単に管理できます。
* 🛠️ **豊富なコマンド群:** 天気予報、ボットの統計情報表示、会話履歴のリセットなど、実用的なコマンドを備えています。
* ⚖️ **レート制限:** ユーザーごとのリクエスト数を制限し、APIの乱用を防ぎます。
* 📂 **モジュール化された構造 (Cogs):** `nextcord.py`のCog機能を活用し、コマンドや機能をファイルごとに整理しているため、メンテナンスや機能追加が容易です。

## 動作に必要なもの

このボットを動かすには、以下の環境が必要です。

* **Python 3.10** 以降
* **Ollama:** [公式サイト](https://ollama.com/) からダウンロードし、お使いのPCにインストールしてください。
* **Ollamaで利用する言語モデル:** 例: `ollama pull gemma:2b`
* **Discordボットアカウント:**
    * [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーションを作成し、ボットを作成してください。
    * **Bot Token** を取得してください。
    * `Privileged Gateway Intents` の項目で、`MESSAGE CONTENT INTENT` を有効にしてください。
* **(任意) OpenWeatherMap APIキー:** 天気予報機能を利用する場合に、[公式サイト](https://openweathermap.org/api)から取得してください。

## インストールとセットアップ

1.  **リポジトリをクローン**
    ```bash
    git clone [https://github.com/MuraseRyosuke/AIDogDiscordBot.git](https://github.com/MuraseRyosuke/AIDogDiscordBot.git)
    cd AIDogDiscordBot
    ```

2.  **Ollamaのセットアップ**
    * Ollamaをインストールし、アプリケーションを起動しておきます。
    * 使用したい言語モデルをダウンロードしておきます。
        ```bash
        # 例: GoogleのGemma 2Bモデルをダウンロード
        ollama pull gemma:2b
        ```

3.  **Python仮想環境の作成と有効化 (推奨)**
    ```bash
    # 仮想環境を作成
    python -m venv venv

    # 仮想環境を有効化
    # Windowsの場合
    .\venv\Scripts\activate
    # macOS / Linuxの場合
    source venv/bin/activate
    ```

4.  **必要なライブラリをインストール**
    ```bash
    pip install -r requirements.txt
    ```

5.  **設定ファイルの準備**
    * `env.example` ファイルをコピーして、`.env` という名前のファイルを作成します。
    * 作成した `.env` ファイルをテキストエディタで開き、あなたの環境に合わせて各項目（特に必須項目）の値を設定します。

## 設定 (`.env`ファイル)

ボットの動作は `.env` ファイルで管理します。

| 変数名 | 説明 | 設定例 |
| :--- | :--- | :--- |
| **`BOT_TOKEN`** | **(必須)** Discordボットのトークン。 | `"M..."` |
| **`OLLAMA_MODEL_NAME`** | **(必須)** Ollamaで使うモデル名。`ollama list`で確認できます。 | `"gemma:2b"` |
| **`OLLAMA_API_URL`** | **(必須)** Ollama APIのエンドポイント。 | `"http://127.0.0.1:11434/api/generate"` |
| `ADMIN_USER_IDS` | (任意) ボットの管理者ユーザーID。カンマ区切りで複数指定可。 | `"1234567890..."` |
| `BOT_COMMAND_PREFIX` | (任意) コマンドの接頭辞。 | `"!aidog "` |
| `OPENWEATHERMAP_API_KEY`| (任意) 天気予報機能で使うAPIキー。 | `"ab..."` |
| `OLLAMA_TEMPERATURE` | (任意) 応答の創造性の度合い。(0.0-2.0) | `"0.8"` |

## 使い方

1.  **ボットの起動**
    * Windowsの場合は `start_aidog_bot.bat` をダブルクリックします。
    * または、ターミナルで以下のコマンドを実行します。
        ```bash
        python bot_main.py
        ```

2.  **AI犬との対話**
    * ボットを招待したDiscordサーバーで、`@AI犬`のようにメンションして話しかけます。
    * ボットとのダイレクトメッセージ（DM）でも対話できます。

3.  **コマンド一覧**
    デフォルトのプレフィックスは `!aidog ` です。

| コマンド | 説明 |
| :--- | :--- |
| `help` | 利用可能なコマンドの一覧を表示します。 |
| `stats` | ボットの稼働状況やOllamaサーバーの状態を表示します。 |
| `clear` | あなたとの会話履歴をリセットします。 |
| `weather <都市名>` | 指定した都市の現在の天気をお知らせします。 |
| `bone` | AI犬からホネの画像をもらえます。 |
| `reloadcfg` | (管理者のみ) `.env`ファイルの設定を再読み込みします。 |

## プロジェクト構造

ai-dog-bot/
├── cogs/                 # コマンドを機能ごとにまとめたフォルダ (Cog)
│   ├── admin.py          # 管理者用コマンド
│   ├── fun.py            # 天気や画像送信などのコマンド
│   └── general.py        # help, statsなどの一般コマンド
├── utils/                # 補助的な機能モジュール
│   ├── bot_utils.py      # レート制限や統計管理
│   └── conversation_manager.py # 会話履歴管理(SQLite)
├── bot_main.py           # ボットのメインプログラム
├── config.py             # 設定の読み込みと管理
├── .env.example          # 設定ファイルの見本
├── requirements.txt      # 必要なPythonライブラリ一覧
└── README.md             # このファイル

## ライセンス

このプロジェクトは [MITライセンス](https://opensource.org/licenses/MIT) の下で公開されています。
