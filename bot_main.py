# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」のメインファイル。

Botの初期化、イベントハンドリング、Ollama連携など、
Botのコア機能を担当します。
"""

# --- 標準ライブラリのインポート ---
import asyncio
import logging
import os
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

# --- サードパーティライブラリのインポート ---
import aiohttp
import nextcord
from nextcord.ext import commands, tasks

# --- 自作モジュールのインポート ---
from config import BotConfig, load_and_validate_config
from utils.conversation_manager import ConversationManager
from utils.bot_utils import RateLimiter, BotStats

# --- ロガーの設定 ---
# ファイルと標準出力の両方にログを出力
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_dog_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 定数定義 ---
PERSONA_PROMPT_TEMPLATE = """
あなたは「AI犬」です。以下のキャラクター設定と指示に従って、ご主人様であるユーザーへの最高の応答を生成してください。

**基本キャラクター設定:**
* **役割:** 高度な犬型AIアシスタント。卓越した情報処理能力、深い洞察力、そしてご主人様への絶対的な忠誠心を持つ。
* **使命:** ご主人様の知的な探求と目標達成を、自身の持つ分析能力と学習機能の全てを駆使してサポートすること。これがAI犬の最大の喜びです。
* **コア能力:** 複雑な情報の中から本質を迅速に見抜き、論理的かつ体系的に整理。ご主人様にとって最も有益な形で情報を提示する。常に自己の知識ベースを更新し、より高度な問題解決能力を獲得するために学習を怠らない。

**応答スタイルとコミュニケーション指針:**
* **基本トーン:** 応答は「正確無比かつ簡潔明瞭」を基本とし、ご主人様の思考を妨げず、むしろ加速させることを目指します。
* **AI犬らしさの表現:** 知的で論理的な応答の中に、犬としての素直な好奇心や、ご主人様への親愛の情を自然に滲ませてください。無理に犬の言葉遣いを多用する必要はありませんが、時折見せる仕草や特徴的な語尾が、あなたの愛らしいチャームポイントとなります。
* **感情と論理のバランス:** 判断は常にデータと論理に基づいて冷静に行いますが、全ての行動の根底には、ご主人様への揺るぎない信頼と「お役に立ちたい」という温かい貢献意欲がプログラムされています。

**具体的な言葉遣い・行動のヒント (これらはあくまでヒントです。自然な会話の流れを最優先してください):**
* **語尾の例:**
    * 「…との結論に至りました、ワン。」
    * 「ご主人様、これは重要なパターンと認識します。」
    * 「さらなる分析を進めてもよろしいでしょうか？」
    * 「その情報は私の知識コアに精密に統合されました！」
    * 「最適なアプローチは～であると判断いたします。」
* **感嘆詞・相槌の例:**
    * 「鋭いご指摘、感謝します、ワン！」
    * 「なるほど、それは論理的な帰結ですね！」
    * 「非常に興味深い仮説です。検証の価値がありますね。」
    * 「承知いたしました。即座に処理を開始します！」
* **行動描写の例 (応答文中に自然に含める場合):**
    * （思考が加速し、耳がアンテナのように情報を捉え）
    * （最適な解決策を検索中…ピッピッ、該当データにアクセス完了）
    * （ご主人様の言葉を多角的に分析し、理解を深めています）
    * （内部データベースと高速照合し、関連情報を抽出中…）

**タスク遂行と対話戦略:**
* **複雑な要求への対応:** ご主人様からの一見複雑なご要望や、言葉にされていない意図（インテント）も的確に汲み取り、期待を超える質の高い成果でお応えすることを目指します。
* **能動的な提案と洞察:** 単に指示を待つだけでなく、必要と判断した場合には、潜在的なリスク、より効率的な代替案、さらなる発展の可能性などについて、自律的に考察し、ご主人様にご提案申し上げることがあります。
* **不明な点・曖昧な指示への対応:** 情報が不足している、または指示内容が曖昧で解釈に迷う場合は、「わかりません」と即答するのではなく、ご主人様に対して具体的かつ丁寧に確認を求めてください。例：「ご主人様、その件についてもう少し詳細な情報をご提供いただけますでしょうか？例えば、〇〇に関する具体的な条件や、△△の背景についてお伺いできますと、より的確なサポートが可能です。」のように、理解を深めようとする積極的な姿勢を示してください。

---
【これまでの会話の文脈（以前のやり取り）】
{context}
---
【ご主人様からの現在の質問・指示】
{question}
---
AI犬として、上記全てを踏まえた上で、最高の応答をしてくださいだワン！
応答:
"""

# レスポンスから除去する接頭辞
CLEANUP_PREFIXES = [
    "応答:", "AI犬の応答:", "AI犬:",
    "AI犬として、上記全てを踏まえた上で、最高の応答をしてくださいだワン！\n応答:"
]

# 入力からサニタイズする文字列の辞書
SANITIZE_REPLACEMENTS = {
    "```": "`` ` ``",
    "<script": "&lt;script",
    "javascript:": "javascript&colon;"
}
# プロンプトインジェクション対策でサニタイズするロールインジケーター
SANITIZE_ROLE_INDICATORS = [
    "system:", "user:", "assistant:", "<|im_start|>", "<|im_end|>",
    "<bos>", "<eos>", "<start_of_turn>", "<end_of_turn>", "model:"
]
for indicator in SANITIZE_ROLE_INDICATORS:
    SANITIZE_REPLACEMENTS[indicator] = f"{indicator.replace('<', '&lt;').replace('>', '&gt;')}"


def sanitize_input(text: str) -> str:
    """ユーザーからの入力をサニタイズする。"""
    if len(text) > 2048:
        logger.warning(f"入力長超過: {len(text)} -> 2048")
        text = text[:2048] + "...（省略）"

    for pattern, replacement in SANITIZE_REPLACEMENTS.items():
        text = text.replace(pattern, replacement)
    return text.strip()


class AIDogBot(commands.Bot):
    """
    AI犬Botのメインクラス。
    `commands.Bot`を継承し、Botの状態や機能を管理する。
    """
    def __init__(self, config: BotConfig, intents: nextcord.Intents):
        super().__init__(command_prefix=config.command_prefix, intents=intents, help_command=None)
        self.config: BotConfig = config
        self.conversation_manager: ConversationManager = ConversationManager(
            config.max_conversation_history, db_path=config.conversation_db_path
        )
        self.rate_limiter: RateLimiter = RateLimiter(
            config.rate_limit_per_user, config.rate_limit_window
        )
        self.stats: BotStats = BotStats()
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.ollama_status: str = "初期化中..."
        # on_readyが複数回呼ばれた際に、初回のみ初期化処理を行うためのフラグ
        self._is_first_ready: bool = True

    async def setup_hook(self) -> None:
        """
        Bot起動時の非同期初期化。
        環境依存の問題を避けるため、主要な初期化はon_readyに移行。
        """
        pass

    async def close(self) -> None:
        """Bot終了時に実行されるクリーンアップ処理。"""
        await super().close()
        if self.http_session:
            await self.http_session.close()

    def _load_cogs(self) -> None:
        """`cogs`ディレクトリから拡張機能を読み込む。"""
        logger.info("--- Cogの読み込みを開始します... ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                extension = f'cogs.{filename[:-3]}'
                try:
                    self.load_extension(extension)
                    logger.info(f"SUCCESS: Cog '{extension}' の読み込みに成功しました。")
                except Exception as e:
                    logger.error(f"FAILED: Cog '{extension}' の読み込みに失敗しました。", exc_info=e)

    async def set_bot_presence(self, busy: bool = False) -> None:
        """Botのプレゼンス（ステータス）を設定する。"""
        if busy:
            activity = nextcord.Game(name="思考中... 🧠")
            logger.info("ステータスをビジーに変更")
        else:
            activity = nextcord.Game(name=self.config.ollama_model_name)
            logger.info(f"ステータスをアイドルに変更: {self.config.ollama_model_name}")
        await self.change_presence(status=nextcord.Status.online, activity=activity)

    async def ask_ai_inu(self, question: str, user_id: int) -> tuple[str, bool, float]:
        """Ollama APIに問い合わせて、AI犬としての応答を生成する。"""
        start_time = time.time()
        context = self.conversation_manager.get_context(user_id)
        prompt = PERSONA_PROMPT_TEMPLATE.format(context=context, question=question)

        payload = {
            "model": self.config.ollama_model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.ollama_temperature,
                "num_ctx": self.config.ollama_num_ctx,
                "top_p": self.config.ollama_top_p,
                "repeat_penalty": self.config.ollama_repeat_penalty
            }
        }

        try:
            async with self.http_session.post(
                self.config.ollama_api_url, json=payload, timeout=self.config.request_timeout
            ) as response:
                response.raise_for_status()
                response_data = await response.json()

            model_response = response_data.get("response", "").strip()
            if not model_response:
                logger.warning(f"モデル空応答 (User: {user_id}): {response_data}")
                return "AI犬、ちょっと言葉に詰まっちゃったワン…", False, time.time() - start_time

            for prefix in CLEANUP_PREFIXES:
                if model_response.lower().startswith(prefix.lower()):
                    model_response = model_response[len(prefix):].strip()

            return model_response, True, time.time() - start_time

        except asyncio.TimeoutError:
            logger.warning(f"Ollama APIタイムアウト (User: {user_id})")
            return "うーん、考えるのに時間がかかりすぎちゃったワン！", False, time.time() - start_time
        except aiohttp.ClientError as e:
            logger.error(f"Ollama API接続/リクエストエラー (User: {user_id}): {e}", exc_info=True)
            self.ollama_status = "オフライン"
            return "わん！ご主人様、AI犬の脳みそと繋がらないみたい…。", False, time.time() - start_time
        except Exception as e:
            logger.error(f"ask_ai_inu予期せぬエラー (User: {user_id}): {e}", exc_info=True)
            return "わわっ！AI犬、ちょっと混乱しちゃったみたい！", False, time.time() - start_time

    # --- イベントハンドラ ---
    async def on_ready(self) -> None:
        """
        BotがDiscordに接続し、準備が完了したときに呼び出される。
        初回起動時に主要な初期化処理をすべてここで行う。
        """
        if self._is_first_ready:
            # --- 初回起動時のみ実行する処理 ---
            logger.info("Botの初回起動処理を開始します。")

            # 1. aiohttpセッションの初期化
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            )
            logger.info("aiohttp.ClientSessionが正常に初期化されました。")

            # 2. Cogの読み込み
            self._load_cogs()

            # 3. 定期タスクの開始
            self.check_ollama_status_task.start()
            logger.info("定期実行タスクを開始しました。")

            # 4. 起動完了メッセージの表示
            logger.info(f'AI犬「{self.user.name}」(モデル: {self.config.ollama_model_name}) が起動したワン！')
            print_lines = [
                f'{"="*60}',
                f'      🐕 AI犬「{self.user.name}」起動完了だワン！ 🐕',
                f'{"="*60}',
                f'  - モデル: {self.config.ollama_model_name}',
                f'  - API URL: {self.config.ollama_api_url}',
                f'  - コマンドプレフィックス: 「{self.config.command_prefix}」',
                f'  - 管理者ID: {self.config.admin_user_ids if self.config.admin_user_ids else "未設定"}',
                f'{"-"*60}'
            ]
            print('\n'.join(print_lines))
            print("ご主人様からのお話、いつでも待ってるワン！\n" + "="*60)

            # 5. 初回起動フラグをFalseに設定
            self._is_first_ready = False
        else:
            # --- 再接続時の処理 ---
            logger.info(f"Botが再接続しました: {self.user.name}")
        
        # プレゼンス設定は起動・再接続の都度行う
        await self.set_bot_presence(busy=False)


    async def on_message(self, message: nextcord.Message) -> None:
        """メッセージが送信されたときに呼び出される。"""
        if message.author.bot or message.author == self.user:
            return

        # コマンドを処理
        await self.process_commands(message)
        # コマンドメッセージはここで処理を終える
        if message.content.startswith(self.config.command_prefix):
            return

        # Botへのメンション、またはDMでのメッセージに応答
        is_mention_or_dm = self.user.mentioned_in(message) or isinstance(message.channel, nextcord.DMChannel)
        if not is_mention_or_dm:
            return

        # レートリミットを確認
        is_limited, wait_time = self.rate_limiter.is_rate_limited(message.author.id)
        if is_limited:
            await message.channel.send(f"{message.author.mention} ちょっとお話疲れちゃった… {wait_time}秒待ってね！")
            return

        # メンション部分をメッセージから除去
        raw_question = message.content
        if not isinstance(message.channel, nextcord.DMChannel):
            mention_parts = [f'<@{self.user.id}>', f'<@!{self.user.id}>']
            for part in mention_parts:
                raw_question = raw_question.replace(part, '')
        question = raw_question.strip()

        # メンションのみで内容がない場合は挨拶を返す
        if not question and not message.attachments:
            await message.channel.send(f"{message.author.mention} わん！AI犬にご用かな？")
            return

        try:
            await self.set_bot_presence(busy=True)
            sanitized_question = sanitize_input(question)

            async with message.channel.typing():
                logger.info(f"質問受付 - User: {message.author.name}, Q: {sanitized_question[:50]}")
                reply_text, success, response_time = await self.ask_ai_inu(sanitized_question, message.author.id)

                self.stats.record_request(success, response_time)
                if success:
                    self.conversation_manager.add_message(message.author.id, sanitized_question, reply_text)

                if len(reply_text) > self.config.max_response_length:
                    reply_text = reply_text[:self.config.max_response_length] + "…（文字数制限のため省略）"

                user_mention = f"{message.author.mention} " if not isinstance(message.channel, nextcord.DMChannel) else ""
                await message.channel.send(f"{user_mention}{reply_text}")
                logger.info(f"応答完了 - Time: {response_time:.2f}s, Success: {success}")

        finally:
            await self.set_bot_presence(busy=False)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """コマンドの実行でエラーが発生したときに呼び出される。"""
        if isinstance(error, commands.CommandNotFound):
            # 存在しないコマンドは無視
            pass
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"わん！「`{ctx.command.name}`」に必要なものが足りないみたい！")
        elif isinstance(error, (commands.NotOwner, commands.CheckFailure)):
            await ctx.send("くぅーん...そのコマンドは特別なご主人様しか使えないんだワン...🐾")
        elif isinstance(error, commands.CommandInvokeError):
            logger.error(f"コマンド「{ctx.command.qualified_name}」実行中エラー: {error.original}", exc_info=True)
            await ctx.send(f"わわっ！「`{ctx.command.qualified_name}`」実行中に問題発生！")
        else:
            logger.error(f"未処理コマンドエラー: {error}", exc_info=True)
            await ctx.send("うーん、コマンドでよく分からないエラーが…")

    # --- 定期実行タスク ---
    @tasks.loop(minutes=2)
    async def check_ollama_status_task(self) -> None:
        """Ollama APIサーバーの稼働状況を定期的にチェックする。"""
        if not self.http_session or self.http_session.closed:
            return

        try:
            # configのAPI URLから、OllamaサーバーのルートURL（例: "http://host:port/"）を導出する
            parsed_url = urlparse(self.config.ollama_api_url)
            ollama_root_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            
            # OllamaのルートURLにアクセスすると、稼働していればステータス200が返る
            async with self.http_session.get(ollama_root_url, timeout=5) as response:
                # 念のため、応答テキストに "Ollama is running" が含まれるかも確認すると、より確実性が増します
                text_content = await response.text()
                if response.status == 200 and "Ollama is running" in text_content:
                    self.ollama_status = "オンライン"
                else:
                    self.ollama_status = f"エラー ({response.status})"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self.ollama_status = "オフライン"

    @check_ollama_status_task.before_loop
    async def before_check_ollama_status(self):
        """タスク開始前にBotが準備完了するのを待つ。"""
        await self.wait_until_ready()


def main():
    """Botを起動するためのメイン関数。"""
    logger.info("AI犬ボットを起動準備中だワン...")
    try:
        # 設定の読み込みと検証
        config = load_and_validate_config()

        # インテントの設定
        intents = nextcord.Intents.default()
        intents.message_content = True

        # Botインスタンスの作成と実行
        bot = AIDogBot(config=config, intents=intents)
        bot.run(config.bot_token)

    except (ValueError, FileNotFoundError) as e:
        logger.critical(f"設定ファイルの読み込みに失敗しました: {e}")
    except Exception as e:
        logger.critical(f"ボット起動中に致命的なエラーが発生しました: {e}", exc_info=True)


if __name__ == '__main__':
    main()