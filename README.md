# 🐾 AI犬 Discord Bot

**あなたの知的好奇心をサポートする、忠実な犬型AIアシスタント**

---

## 概要

**AI犬**は、ローカルで動作する大規模言語モデル（LLM）と連携し、Discord上で高度な対話や情報検索を提供する多機能Botです。Ollamaを利用することで、外部のAPIサービスに依存しない、プライベートでカスタマイズ可能なAIチャット体験を実現します。

「ご主人様のお役に立ちたい」という一途な思いで、あなたの知的探求と目標達成を全力でサポートします。

## ✨ 主要な機能

* **🧠 高度なAIチャット機能**
    * **自然言語対話:** メンションやダイレクトメッセージ（DM）で、文脈を理解した自然な会話が可能です。
    * **永続的な記憶:** SQLiteデータベースを利用し、ユーザーごとの会話履歴を記憶。Botを再起動しても会話が引き継がれます。
    * **キャラクター性:** 「AI犬」としてのペルソナに基づいた、忠実で愛らしい応答を返します。

* **🛠️ 多彩なコマンド機能**
    * **NDL（国立国会図書館）検索:** 書籍、歴史資料、地図などの学術情報を検索できます。書影を使ったクイズ機能も搭載。
    * **グルメ検索:** ホットペッパーグルメAPIと連携し、指定したキーワードで飲食店を検索したり、ランダムでお店を提案したりします。
    * **天気予報:** OpenWeatherMap APIと連携し、指定した都市の現在の天気を知らせます。
    * **Bot管理:** 稼働状況の確認、会話履歴のリセット、設定の動的リロード（管理者向け）など、運用に必要な機能も充実しています。

* **⚙️ 堅牢な設計**
    * **レートリミット:** ユーザーごとのコマンド実行頻度を制限し、APIの乱用を防ぎます。
    * **非同期処理:** `nextcord`と`aiohttp`を活用した完全な非同期設計により、スムーズな応答を実現します。
    * **モジュール化:** `Cogs`を利用して機能ごとにコードが整理されており、メンテナンスや機能拡張が容易です。

## 動作に必要なもの

このBotを動作させるには、以下のソフトウェアとAPIキーが必要です。

* **[Ollama](https://ollama.com/)**: ローカルでLLMを動かすための必須ツール。
* **[Python](https://www.python.org/)**: 3.8以上を推奨。
* **Discord Bot Token**: あなたのBotの認証トークン。
* **各種APIキー (任意)**:
    * [OpenWeatherMap API Key](https://openweathermap.org/api) (天気機能に必要)
    * [ホットペッパー Webサービス APIキー](https://webservice.recruit.co.jp/doc/hotpepper/index.html) (グルメ検索機能に必要)

## 🚀 セットアップと起動方法

以下の手順に従って、AI犬をあなたのサーバーで動かすことができます。

### Step 1: リポジトリのクローン
まず、このリポジトリをローカルマシンにクローンします。
**注:** 以下のコマンドのURL部分は、ご自身で作成したGitHubリポジトリのURLに置き換えてください。
```bash
git clone [https://github.com/your-username/ai-dog-discord-bot.git](https://github.com/your-username/ai-dog-discord-bot.git)
cd ai-dog-discord-bot
```

### Step 2: Python仮想環境のセットアップ
プロジェクト用の独立したPython環境を作成することを強く推奨します。

**Windows:**
```shell
python -m venv venv
.\venv\Scripts\activate
```

**macOS / Linux:**
```shell
python3 -m venv venv
source venv/bin/activate
```

### Step 3: 依存ライブラリのインストール
必要なPythonライブラリをインストールします。
```shell
pip install -r requirements.txt
```

### Step 4: Ollamaのセットアップ
Ollamaを公式サイトからインストールし、使用したい言語モデルを準備します。
```shell
# 例: デフォルトで想定しているモデルを準備する場合
ollama pull mmnga/sarashina2.2-3b-instruct-v0.1-gguf
```
Ollamaがバックグラウンドで起動していることを確認してください。

### Step 5: 環境変数ファイル (`.env`) の準備
プロジェクトのルートにある`.env.example`をコピーして、`.env`という名前のファイルを作成します。
```shell
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
作成した`.env`ファイルを開き、あなたの環境に合わせて各項目を編集します。**このファイルは機密情報なので、絶対に公開しないでください。**

```ini
# .env
BOT_TOKEN="あなたのDiscord Botトークン"
OLLAMA_MODEL_NAME="使用するOllamaモデル名"
OLLAMA_API_URL="[http://127.0.0.1:11434/api/generate](http://127.0.0.1:11434/api/generate)"
ADMIN_USER_IDS="あなたのDiscordユーザーID"
OPENWEATHERMAP_API_KEY="あなたのOpenWeatherMap APIキー"
HOTPEPPER_API_KEY="あなたのホットペッパー APIキー"
... # その他の設定
```

### Step 6: Discord Botの準備
1.  **Botの作成:** [Discord Developer Portal](https://discord.com/developers/applications)で新しいアプリケーションを作成し、「Bot」タブからBotユーザーを追加してトークンをコピーします。
2.  **インテントの有効化:** 「Bot」タブの「Privileged Gateway Intents」セクションで、**`MESSAGE CONTENT INTENT`** を必ず有効にしてください。
3.  **サーバーへの招待:** 「OAuth2 > URL Generator」で、スコープに`bot`と`applications.commands`を選択し、必要な権限（最低限「チャンネルを見る」「メッセージを送信」「埋め込みリンク」など）を付与して、生成されたURLからあなたのサーバーにBotを招待します。

### Step 7: Botの起動
すべての準備が整ったら、Botを起動します。

**Windows:**
```shell
# start_aidog_bot.batをダブルクリックするか、コンソールで実行
.\start_aidog_bot.bat
```

**macOS / Linux:**
```shell
python3 bot_main.py
```

コンソールに「起動完了だワン！」というメッセージが表示され、Discord上でBotがオンラインになれば成功です！

## コマンド一覧

デフォルトのコマンドプレフィックスは `!aidog ` です。（末尾にスペースが必要です）

| コマンド                                     | 説明                                                 |
| -------------------------------------------- | ---------------------------------------------------- |
| `!aidog help`                                | ヘルプメッセージを表示します。                       |
| `!aidog stats`                               | Botの稼働状況や統計情報を表示します。                 |
| `!aidog clear`                               | あなたとの会話履歴をリセットします。                 |
| `!aidog weather <都市名>`                      | 指定された都市の天気予報をお知らせします。           |
| `!aidog bone`                                | AI犬からホネの画像をプレゼントします。               |
| `!aidog gourmet <キーワード>`                  | キーワードに合う飲食店を検索します。                 |
| `!aidog randomgourmet <キーワード>`            | ランダムで飲食店を1件提案します。                    |
| `!aidog ndl search <キーワード>`             | 国立国会図書館から書籍や資料を検索します。           |
| `!aidog ndl random`                          | おすすめの本をランダムで1冊紹介します。              |
| `!aidog ndl quiz`                            | 書影を見て本のタイトルを当てるクイズを出題します。   |
| `!aidog reloadcfg`                           | **(管理者のみ)** Botの設定を再読み込みします。       |

## 謝辞

このプロジェクトは、以下の素晴らしいサービスとAPIを利用して実現しています。

* [Ollama](https://ollama.com/)
* [nextcord](https://nextcord.dev/)
* [国立国会図書館サーチ](https://iss.ndl.go.jp/)
* [ホットペッパー Webサービス](https://webservice.recruit.co.jp/)
* [OpenWeatherMap](https://openweathermap.org/)

## ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。
