import nextcord
from nextcord.ext import commands, tasks
import requests
import json
import os
import asyncio
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple # Optional, Tuple を追加
from dataclasses import dataclass, field # field を追加
from dotenv import load_dotenv
# hashlib は現在使用されていませんが、将来的に何らかのハッシュ計算が必要になった場合のためにコメントアウトで残します
# import hashlib

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_dog_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 環境変数読み込み
load_dotenv()

# 設定クラス
@dataclass
class BotConfig:
    bot_token: str
    ollama_model_name: str
    ollama_api_url: str
    command_prefix: str = "!aidog " # .envから読むように変更したのでデフォルト値を設定
    max_conversation_history: int = 5
    request_timeout: int = 180 # デフォルト値を長めに変更
    rate_limit_per_user: int = 5 # デフォルト値を変更
    rate_limit_window: int = 60
    max_response_length: int = 1900
    admin_user_ids: List[int] = field(default_factory=list) # default_factoryを使用

    # Ollama パラメータ (コード内でデフォルト値を設定)
    ollama_temperature: float = 0.7
    ollama_num_ctx: int = 4096
    ollama_top_p: float = 0.9
    ollama_repeat_penalty: float = 1.1
    progress_update_interval: int = 7 # 進捗表示の更新間隔(秒)

# 設定読み込みと検証
def load_and_validate_config() -> BotConfig: # 関数名を変更し、検証を強化
    # 必須項目
    bot_token_env = os.getenv("BOT_TOKEN")
    ollama_model_name_env = os.getenv("OLLAMA_MODEL_NAME")
    ollama_api_url_env = os.getenv("OLLAMA_API_URL")

    if not bot_token_env or not ollama_model_name_env or not ollama_api_url_env:
        missing = []
        if not bot_token_env: missing.append("BOT_TOKEN")
        if not ollama_model_name_env: missing.append("OLLAMA_MODEL_NAME")
        if not ollama_api_url_env: missing.append("OLLAMA_API_URL")
        logger.critical(f"致命的エラー: 必須の環境変数が設定されていません: {', '.join(missing)}")
        exit(1) # 必須項目がない場合は起動しない

    # 管理者IDの処理
    admin_ids = []
    admin_user_ids_env = os.getenv("ADMIN_USER_IDS")
    if admin_user_ids_env:
        try:
            # カンマ区切りで、各IDの前後の空白を除去し、空でなければintに変換
            admin_ids = [int(x.strip()) for x in admin_user_ids_env.split(",") if x.strip().isdigit()]
            if not admin_ids and admin_user_ids_env: # 何か入力はあるが有効なIDがなかった場合
                 logger.warning("ADMIN_USER_IDS が設定されていますが、有効な数値のIDが含まれていません。空として扱います。")
        except ValueError:
            logger.warning("ADMIN_USER_IDS の形式が不正です。カンマ区切りの数値で指定してください。例: \"123,456\"。空として扱います。")
            admin_ids = [] # エラー時は空リストに

    # BotConfigインスタンスの作成と他の設定の読み込み
    config_instance = BotConfig(
        bot_token=bot_token_env,
        ollama_model_name=ollama_model_name_env,
        ollama_api_url=ollama_api_url_env,
        admin_user_ids=admin_ids
    )

    # オプショナルな設定項目 (型変換とデフォルト値の適用)
    config_instance.command_prefix = os.getenv("BOT_COMMAND_PREFIX", config_instance.command_prefix)
    config_instance.max_conversation_history = int(os.getenv("MAX_CONVERSATION_HISTORY", str(config_instance.max_conversation_history)))
    config_instance.request_timeout = int(os.getenv("REQUEST_TIMEOUT", str(config_instance.request_timeout)))
    config_instance.rate_limit_per_user = int(os.getenv("RATE_LIMIT_PER_USER", str(config_instance.rate_limit_per_user)))
    config_instance.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", str(config_instance.rate_limit_window)))
    config_instance.max_response_length = int(os.getenv("MAX_RESPONSE_LENGTH", str(config_instance.max_response_length)))
    
    config_instance.ollama_temperature = float(os.getenv("OLLAMA_TEMPERATURE", str(config_instance.ollama_temperature)))
    config_instance.ollama_num_ctx = int(os.getenv("OLLAMA_NUM_CTX", str(config_instance.ollama_num_ctx)))
    config_instance.ollama_top_p = float(os.getenv("OLLAMA_TOP_P", str(config_instance.ollama_top_p)))
    config_instance.ollama_repeat_penalty = float(os.getenv("OLLAMA_REPEAT_PENALTY", str(config_instance.ollama_repeat_penalty)))
    config_instance.progress_update_interval = int(os.getenv("PROGRESS_UPDATE_INTERVAL", str(config_instance.progress_update_interval)))

    return config_instance


# 会話履歴管理クラス
class ConversationManager:
    def __init__(self, max_history: int = 5):
        self.conversations: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.max_history = max_history
    
    def add_message(self, user_id: int, user_msg: str, bot_response: str):
        self.conversations[user_id].append({
            'user': user_msg,
            'assistant': bot_response,
            'timestamp': datetime.now()
        })
    
    def get_context(self, user_id: int) -> str:
        if user_id not in self.conversations or not self.conversations[user_id]:
            return ""
        
        context_parts = []
        for msg in self.conversations[user_id]:
            if datetime.now() - msg['timestamp'] > timedelta(hours=1): # 1時間以上前の履歴は古すぎると判断
                continue
            context_parts.append(f"以前のご主人様の質問: {msg['user'][:150]}")
            context_parts.append(f"以前のAI犬の応答: {msg['assistant'][:150]}")
        
        # 直近3往復(6要素)の会話を使用。新しいものが後になるように。
        return "\n".join(context_parts) if context_parts else "" # maxlenで制限されているのでこれでOK
    
    def clear_user_history(self, user_id: int):
        if user_id in self.conversations:
            self.conversations[user_id].clear()
            logger.info(f"ユーザーID {user_id} の会話履歴をクリアしました。")

# レート制限管理クラス
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[int, deque] = defaultdict(deque)
    
    def is_rate_limited(self, user_id: int) -> Tuple[bool, int]:
        now = time.time()
        user_requests = self.requests[user_id]
        
        while user_requests and now - user_requests[0] > self.window_seconds:
            user_requests.popleft()
        
        if len(user_requests) >= self.max_requests:
            wait_time = int(self.window_seconds - (now - user_requests[0]) + 1)
            return True, wait_time
        
        user_requests.append(now)
        return False, 0

# 統計管理クラス
class BotStats:
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_response_time = 0.0
        self.start_time = datetime.now()
    
    def record_request(self, success: bool, response_time: float):
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            self.total_response_time += response_time
        else:
            self.failed_requests += 1
    
    def get_stats(self) -> dict:
        uptime_delta = datetime.now() - self.start_time
        uptime_str = str(timedelta(seconds=int(uptime_delta.total_seconds())))
        avg_response_time = (self.total_response_time / self.successful_requests 
                             if self.successful_requests > 0 else 0)
        
        return {
            'uptime': uptime_str,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{(self.successful_requests/self.total_requests*100):.1f}%" if self.total_requests > 0 else "N/A",
            'avg_response_time': f"{avg_response_time:.2f}s"
        }

# AI犬ボットクラス
class AIDogBot(commands.Bot):
    def __init__(self, config: BotConfig):
        intents = nextcord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=config.command_prefix, intents=intents, help_command=None) # help_command=None でデフォルトを無効化
        
        self.config = config
        self.conversation_manager = ConversationManager(config.max_conversation_history)
        self.rate_limiter = RateLimiter(config.rate_limit_per_user, config.rate_limit_window)
        self.stats = BotStats()
        self.ollama_status = "初期化中..."
        
        self.persona_prompt_template = """あなたは「AI犬」という名前の、賢くて忠実で愛らしい犬型AIアシスタントです。
ユーザーのことを「ご主人様」と呼ぶことがあります。
あなたの応答は、常に協力的で、親しみやすく、そして犬らしい可愛らしさを自然に表現してください。
例えば、以下のような言葉遣いや振る舞いを参考に、あなた自身の言葉で話してください。
- 語尾の例: 「～だワン！」「～なのだ！」「～かな？」「～してみるワン！」
- 感嘆詞の例: 「わん！」「くぅーん」「わふわふ」「きゃん！」「がおー！」
- 行動描写の例: （しっぽを振って)」「(首をかしげて)」「(くんくんと匂いを嗅いで)」

【会話の文脈（以前のやり取り）】
{context}

【ご主人様からの現在の質問・指示】
{question}

AI犬として、最高の応答をしてくださいだワン！
応答: """

    async def setup_hook(self):
        self.check_ollama_status_task.start()
        logger.info(f"AI犬ボット「{self.user.name if self.user else 'AI犬'}」の初期化処理(setup_hook)が完了しました")

    @tasks.loop(minutes=2)
    async def check_ollama_status_task(self):
        try:
            ollama_base_url = self.config.ollama_api_url.replace("/api/generate", "")
            if not ollama_base_url.endswith('/'): ollama_base_url += '/'
            
            async with requests.Session() as session: # type: ignore
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: session.get(ollama_base_url, timeout=5)
                )
            self.ollama_status = "オンライン" if response.status_code == 200 else f"エラー ({response.status_code})"
        except requests.exceptions.ConnectionError:
            self.ollama_status = "オフライン (接続不可)"
        except requests.exceptions.Timeout:
            self.ollama_status = "オフライン (タイムアウト)"
        except Exception as e:
            self.ollama_status = "不明 (チェックエラー)"
            logger.warning(f"Ollama状態チェック失敗: {e}")

    @check_ollama_status_task.before_loop
    async def before_check_ollama_status(self):
        await self.wait_until_ready()
        logger.info("Ollama状態チェックループを開始します。")

    async def ask_ai_inu(self, question: str, user_id: int) -> Tuple[str, bool, float]:
        start_time = time.time()
        try:
            context = self.conversation_manager.get_context(user_id)
            prompt = self.persona_prompt_template.format(
                context=context if context else "特に以前のやり取りはありませんワン。",
                question=question
            )
            
            payload = {
                "model": self.config.ollama_model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.ollama_temperature,
                    "num_ctx": self.config.ollama_num_ctx,
                    "top_p": self.config.ollama_top_p,
                    "repeat_penalty": self.config.ollama_repeat_penalty,
                }
            }
            headers = {"Content-Type": "application/json"}
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.config.ollama_api_url,
                    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                    headers=headers,
                    timeout=self.config.request_timeout
                )
            )
            response.raise_for_status()
            response_data = response.json()
            model_response = response_data.get("response", "").strip()
            
            if not model_response:
                logger.warning(f"モデルからの空応答 (ユーザーID: {user_id}): {response_data}")
                return "うーん、AI犬、言葉が出てこないワン…もう一度聞いてほしいワン！", False, time.time() - start_time
            
            cleanup_prefixes = ["応答:", "AI犬の応答:", "AI犬:", self.persona_prompt_template.split("{question}")[-1].split("応答:")[0]+"応答:"]
            original_response_for_logging = model_response[:100] # プレフィックス除去前のログ用
            for prefix in cleanup_prefixes:
                if model_response.lower().startswith(prefix.lower()):
                    model_response = model_response[len(prefix):].strip()
            if len(original_response_for_logging) != len(model_response[:100]):
                 logger.info(f"応答プレフィックス除去: '{original_response_for_logging}' -> '{model_response[:100]}'")

            response_time = time.time() - start_time
            return model_response, True, response_time
            
        except requests.exceptions.Timeout:
            logger.warning(f"Ollama APIタイムアウト (ユーザーID: {user_id}, 質問: {question[:50]})")
            return "うーん、考えるのに時間がかかりすぎちゃったワン！ご主人様、もう一度試してみてほしいワン！", False, time.time() - start_time
        except requests.exceptions.ConnectionError:
            logger.error(f"Ollama API接続エラー (ユーザーID: {user_id})")
            self.ollama_status = "オフライン (接続失敗)"
            return "わん！Ollamaサーバーと繋がらないみたいだワン…ご主人様、管理者さんに伝えてもらえるかな？", False, time.time() - start_time
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama APIリクエストエラー (ユーザーID: {user_id}, 質問: {question[:50]}): {e}")
            return f"ご主人様！AI犬の頭脳（モデル「{self.config.ollama_model_name}」）とのお話に失敗しちゃったワン…ちょっと調子が悪いみたいだワン。", False, time.time() - start_time
        except Exception as e:
            logger.error(f"ask_ai_inu での予期せぬエラー (ユーザーID: {user_id}, 質問: {question[:50]}): {e}", exc_info=True)
            return "わわっ！何か大変なことが起きたみたいだワン！ご主人様、ちょっと時間を置いてからもう一度試してほしいワン！", False, time.time() - start_time

    def sanitize_input(self, text: str) -> str:
        if len(text) > 2048:
            logger.warning(f"入力長超過: {len(text)}文字 -> 2048文字に切り詰め")
            text = text[:2048] + "...（ご主人様、お話が長すぎるのでちょっと省略するワン！）"
        
        replacements = { "```": "`` ` ``", "<script": "&lt;script", "javascript:": "javascript&colon;" }
        # モデルのプロンプトを混乱させる可能性のある一般的な役割指示子は、ユーザー入力からは除去またはエスケープ
        # これらはGemmaのチャットテンプレートで使われることがあるため、ユーザーが意図せず入力した場合に影響を減らす
        role_indicators = ["system:", "user:", "assistant:", "<|im_start|>", "<|im_end|>", "<bos>", "<eos>", "<start_of_turn>", "<end_of_turn>", "model:"]
        for indicator in role_indicators:
            replacements[indicator] = f"{indicator.replace('<', '&lt;').replace('>', '&gt;')}" # 簡易エスケープ

        for pattern, replacement in replacements.items():
            text = text.replace(pattern, replacement)
        return text.strip()

    async def handle_user_message(self, message: nextcord.Message, question: str):
        user_id = message.author.id
        sanitized_question = self.sanitize_input(question)
        
        if not sanitized_question:
            await message.channel.send("わん？ご主人様、何かお話ししたいことがあるのかな？")
            return
        
        is_limited, wait_time = self.rate_limiter.is_rate_limited(user_id)
        if is_limited:
            await message.channel.send(
                f"{message.author.mention} AI犬、ちょっとお話疲れちゃったワン…🐾 "
                f"{wait_time}秒くらい休んだらまた元気にお返事できるワン！"
            )
            return
        
        user_mention = f"{message.author.mention} " if not isinstance(message.channel, nextcord.DMChannel) else ""
        thinking_messages = [
            "AI犬がご主人様の言葉を一生懸命考えてるワン！🐕💭", "うーん、どんなお返事が喜んでくれるかな？🤔わくわく！",
            "ご主人様のために、最高の答えを探してるワン！✨", "もうちょっとで考えがまとまるワン！待っててね！⏰"
        ]
        initial_thinking_message = f"{user_mention}{thinking_messages[0]}"
        processing_msg = await message.channel.send(initial_thinking_message)
        
        logger.info(f"質問受付 - ユーザー: {message.author.name} ({user_id}), 質問(加工後): {sanitized_question[:100]}")
        
        progress_task = None
        try:
            progress_task = asyncio.create_task(self.show_progress_async(processing_msg, user_mention, thinking_messages))
            reply_text, success, response_time = await self.ask_ai_inu(sanitized_question, user_id)
            
            if progress_task and not progress_task.done(): progress_task.cancel()
            self.stats.record_request(success, response_time)
            
            if len(reply_text) > self.config.max_response_length:
                reply_text = reply_text[:self.config.max_response_length] + "...わん！（お話が長すぎたから、ちょっと省略したワン！）"
            
            final_response = f"{user_mention}{reply_text}"
            await processing_msg.edit(content=final_response)
            
            if success:
                self.conversation_manager.add_message(user_id, sanitized_question, reply_text)
            logger.info(f"応答完了 - 時間: {response_time:.2f}s, 成功: {success}, 応答長: {len(reply_text)}")
            
        except asyncio.CancelledError:
            logger.info("進捗表示タスクがキャンセルされました。")
        except Exception as e:
            logger.error(f"handle_user_message でのエラー: {e}", exc_info=True)
            if progress_task and not progress_task.done(): progress_task.cancel()
            try:
                await processing_msg.edit(content=f"{user_mention}わわっ！ご主人様、AI犬の中でエラーが起きちゃったみたいだワン！ごめんなさい！")
            except nextcord.NotFound: logger.warning("processing_msg の編集中にメッセージが見つかりませんでした。")
            except Exception as edit_e: logger.error(f"processing_msg の編集エラー: {edit_e}")

    async def show_progress_async(self, message: nextcord.Message, user_mention: str, thinking_messages: List[str]):
        try:
            idx = 0
            while True:
                idx = (idx + 1) % len(thinking_messages)
                current_progress_text = f"{user_mention}{thinking_messages[idx]}"
                try: await message.edit(content=current_progress_text)
                except nextcord.NotFound: logger.warning("進捗表示メッセージが見つかりません。タスク停止。"); break
                except Exception as e_edit: logger.warning(f"進捗表示メッセージ編集失敗: {e_edit}")
                await asyncio.sleep(self.config.progress_update_interval)
        except asyncio.CancelledError: pass
        except Exception as e: logger.error(f"進捗表示タスクでエラー: {e}")

# --- グローバル設定とボットインスタンス ---
config = load_and_validate_config()
bot = AIDogBot(config)
# bot.remove_command('help') # AIDogBotの__init__で help_command=None を設定したので不要

# --- イベントハンドラー (グローバルスコープ) ---
@bot.event
async def on_ready():
    logger.info(f'AI犬「{bot.user.name}」(モデル: {bot.config.ollama_model_name}) が起動しました！')
    print('=' * 60)
    print(f'      🐕 AI犬「{bot.user.name}」起動完了だワン！ 🐕')
    print('=' * 60)
    print(f'🦴 モデル: {bot.config.ollama_model_name}')
    print(f'🔧 API URL: {bot.config.ollama_api_url}')
    print(f'🗣️ コマンドプレフィックス: 「{bot.config.command_prefix}」')
    print(f'⏱️ リクエストタイムアウト: {bot.config.request_timeout}秒')
    print(f'📚 会話履歴保持数: {bot.config.max_conversation_history}往復')
    print(f'⏳ レート制限: {bot.config.rate_limit_per_user}回 / {bot.config.rate_limit_window}秒')
    print(f'📏 最大応答長: {bot.config.max_response_length}文字')
    print(f'👑 管理者ID: {bot.config.admin_user_ids if bot.config.admin_user_ids else "未設定"}')
    print('-' * 60)
    
    try:
        activity_name = "Gemma 2 2B JPNと遊んでるワン！" # ステータスメッセージ変更
        activity = nextcord.Game(name=activity_name)
        await bot.change_presence(status=nextcord.Status.online, activity=activity)
        logger.info(f"AI犬のステータスを「{activity_name}」に設定しました。")
        print(f'🎮 ステータス: {activity_name}')
    except Exception as e:
        logger.error(f"ステータス設定中にエラー: {e}")
        print(f'⚠️ ステータス設定エラー: {e}')
        
    print('-' * 60)
    print("ご主人様からのお話、待ってるワン！")
    print('=' * 60)

@bot.event
async def on_message(message: nextcord.Message):
    if message.author.bot or message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message) or isinstance(message.channel, nextcord.DMChannel):
        raw_question = message.content
        if not isinstance(message.channel, nextcord.DMChannel):
            mention_parts = [f'<@{bot.user.id}>', f'<@!{bot.user.id}>']
            for part in mention_parts:
                raw_question = raw_question.replace(part, '')
        question = raw_question.strip()
        
        if not question and not isinstance(message.channel, nextcord.DMChannel) and bot.user.mentioned_in(message):
            await message.channel.send(f"{message.author.mention} わん！AI犬にご用かな？お気軽にお話ししてほしいワン！🐾")
            return
            
        if question:
            await bot.handle_user_message(message, question)
    
    await bot.process_commands(message)

# --- コマンド定義 (グローバルスコープ) ---
@bot.command(name='stats', help="AI犬ボットの統計情報を表示しますだワン！")
async def show_stats_command(ctx: commands.Context): # 関数名を変更 (クラスメソッドと区別)
    stats_data = bot.stats.get_stats() # グローバルなbotインスタンスを参照
    embed = nextcord.Embed(title="📊 AI犬ボット統計情報 📊", color=0x2ecc71, timestamp=datetime.now())
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.display_avatar else None)
    
    embed.add_field(name="🐕 ボット名", value=bot.user.name, inline=True)
    embed.add_field(name="🧠 使用モデル", value=bot.config.ollama_model_name, inline=True)
    embed.add_field(name="🔌 Ollama状態", value=bot.ollama_status, inline=True)
    embed.add_field(name="⏱️ 稼働時間", value=stats_data['uptime'], inline=True)
    embed.add_field(name="🗣️ 総リクエスト数", value=stats_data['total_requests'], inline=True)
    embed.add_field(name="📈 成功率", value=stats_data['success_rate'], inline=True)
    embed.add_field(name="✅ 成功リクエスト", value=stats_data['successful_requests'], inline=True)
    embed.add_field(name="❌ 失敗リクエスト", value=stats_data['failed_requests'], inline=True)
    embed.add_field(name="⏳ 平均応答時間", value=stats_data['avg_response_time'], inline=True)

    embed.set_footer(text="AI犬は今日も元気に稼働中だワン！")
    await ctx.send(embed=embed)

@bot.command(name='clear', help="AI犬との会話履歴をリセットするワン！")
async def clear_history_command(ctx: commands.Context):
    bot.conversation_manager.clear_user_history(ctx.author.id)
    await ctx.send(f"{ctx.author.mention} ご主人様との今までの思い出、きれいさっぱりリセットしたワン！✨ 新しいお話、いつでも待ってるワン！")

@bot.command(name='help', help="AI犬ボットの使い方がわかるワン！") 
async def custom_help_command(ctx: commands.Context): # 関数名を変更
    embed = nextcord.Embed(title="🐾 AI犬ボット ヘルプだワン！ 🐾", color=0x3498db, timestamp=datetime.now())
    embed.description = f"ご主人様！AI犬の使い方はこんな感じだワン！\nボクのコマンドプレフィックスは「`{bot.config.command_prefix}`」だよ！"
    if bot.user and bot.user.display_avatar: embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(
        name="💬 AI犬とお話しする方法",
        value=f"• AI犬にメンション (`@{bot.user.name}`) + 聞きたいこと\n"
              f"• AI犬にDM（ダイレクトメッセージ）で聞きたいこと",
        inline=False
    )
    embed.add_field(
        name="🛠️ コマンド一覧",
        value=f"• `{bot.config.command_prefix}help` - このヘルプメッセージを表示するワン！\n"
              f"• `{bot.config.command_prefix}stats` - AI犬の元気度（統計情報）をチェック！\n"
              f"• `{bot.config.command_prefix}clear` - 前のお話を忘れて、新しいお話を始めるワン！\n"
              f"• `{bot.config.command_prefix}reloadcfg` - (管理者のみ) 設定を再読み込みするワン！",
        inline=False
    )
    embed.add_field(
        name="📝 ちょっとしたルールだワン！",
        value=f"• レート制限: {bot.config.rate_limit_per_user}回/{bot.config.rate_limit_window}秒\n"
              f"• 会話履歴: {bot.config.max_conversation_history}往復くらいまで記憶\n"
              f"• タイムアウト: {bot.config.request_timeout}秒くらいで応答がなければ、もう一度試してみてワン！",
        inline=False
    )
    embed.set_footer(text="AI犬ともっともっと仲良くなろうワン！")
    await ctx.send(embed=embed)

@bot.command(name='reloadcfg', help="設定を再読み込みします（管理者専用）。")
@commands.is_owner() # Botのオーナーのみが実行可能 (BotConfigのadmin_user_idsと併用も可)
# @commands.has_any_role("管理者", "運営") # 特定ロールを持つ人のみ (ロール名はサーバーに合わせて)
# async def reload_config_command(ctx: commands.Context, *, new_model_name: Optional[str] = None): # モデル名を引数で指定できるようにするなど
async def reload_config_command(ctx: commands.Context):
    # is_owner()を使う場合、以下の手動IDチェックは不要になる
    # if ctx.author.id not in bot.config.admin_user_ids:
    #     await ctx.send("くぅーん...そのコマンドは、特別なご主人様しか使えないんだワン...")
    #     return
    
    try:
        logger.info(f"管理者 {ctx.author.name} ({ctx.author.id}) による設定再読み込み要求。")
        
        # .env ファイルを再読み込み
        load_dotenv(override=True) 
        
        # グローバルな config オブジェクトを新しい設定で更新
        # 注意: この方法は、BotConfigインスタンスの属性を直接書き換えるもので、
        # BotConfigの__init__や__post_init__が再度呼ばれるわけではありません。
        # 起動中のタスクや既存のオブジェクトが古い設定値を持ち続ける可能性があるため、
        # 全ての変更を完全に反映するにはボットの再起動が最も確実です。
        # ここでは、主要な設定を更新する試みです。

        global config # グローバルなconfigを参照・更新するために宣言
        old_config_dict = config.__dict__.copy() # 比較用に古い設定をコピー
        
        config = load_and_validate_config() # グローバルなconfigを新しいインスタンスで上書き
        
        # Botインスタンスが持っているconfigオブジェクトも更新
        bot.config = config 
        
        # Botインスタンスの他の属性も更新
        bot.command_prefix = config.command_prefix # Botインスタンスのcommand_prefixも更新
        bot.conversation_manager = ConversationManager(config.max_conversation_history)
        bot.rate_limiter = RateLimiter(config.rate_limit_per_user, config.rate_limit_window)

        # 変更点をログに出力（例）
        changes = []
        if old_config_dict['ollama_model_name'] != config.ollama_model_name:
            changes.append(f"モデル: {old_config_dict['ollama_model_name']} → {config.ollama_model_name}")
        if old_config_dict['request_timeout'] != config.request_timeout:
            changes.append(f"タイムアウト: {old_config_dict['request_timeout']}s → {config.request_timeout}s")
        # 他の重要な変更も同様にログ出力すると良い

        if changes:
            await ctx.send(f"設定ファイルを再読み込みして、AI犬がパワーアップしたワン！🔋\n変更点: {', '.join(changes)}")
            logger.info(f"設定が管理者 {ctx.author.name} によって更新されました。変更点: {', '.join(changes)}")
        else:
            await ctx.send("設定ファイルは現在の設定と同じだったワン！特に変更はなかったよ。")
            logger.info(f"管理者 {ctx.author.name} が設定を再読み込みしましたが、変更はありませんでした。")
            
    except Exception as e:
        await ctx.send(f"設定の再読み込みに失敗しちゃったワン... ごめんなさい！エラー: {str(e)}")
        logger.error(f"設定再読み込みエラー: {e}", exc_info=True)


# --- エラーハンドラー (グローバルスコープ) ---
@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        # ユーザーが間違ったコマンドを入力したことをログに記録しても良い (ただし頻繁に発生する可能性あり)
        # logger.info(f"不明なコマンドが試されました: {ctx.invoked_with} by {ctx.author.name}")
        await ctx.send(f"あれれ？「`{ctx.invoked_with}`」なんてコマンド、AI犬は知らないワン... 🤔\n`{bot.config.command_prefix}help` で使えるコマンドを確認してほしいワン！")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"わん！コマンドに必要なものが足りないみたいだワン！\n`{bot.config.command_prefix}help {ctx.command.name if ctx.command else ''}` で使い方を確認してね！")
    elif isinstance(error, commands.NotOwner): # is_owner() デコレータからのエラー
        await ctx.send("くぅーん...そのコマンドは、ボクの特別なご主人様だけが使えるんだワン...ごめんね！🐾")
    elif isinstance(error, commands.CommandInvokeError): # コマンド実行中の内部エラー
        logger.error(f"コマンド「{ctx.command.qualified_name if ctx.command else '不明'}」の実行中にエラー: {error.original}", exc_info=True)
        await ctx.send(f"わわっ！「`{ctx.command.qualified_name if ctx.command else '不明なコマンド'}`」の実行中に何か問題が起きちゃったワン！ちょっと待ってからもう一度試してみてね。")
    else: # その他のコマンド関連エラー
        logger.error(f"未処理のコマンドエラー: {error} (コマンド: {ctx.command.qualified_name if ctx.command else '不明'}, タイプ: {type(error)})", exc_info=True)
        await ctx.send("うーん、なんだかよく分からないコマンドのエラーが起きちゃったワン...ごめんなさい！")

# --- メイン実行 ---
if __name__ == '__main__':
    try:
        logger.info("AI犬ボットを起動準備中だワン...")
        bot.run(config.bot_token) # グローバルなconfigを参照
    except KeyboardInterrupt:
        logger.info("AI犬ボットがご主人様によっておやすみさせられました。またねだワン！💤")
    except nextcord.errors.LoginFailure:
        logger.critical("致命的エラー: Discordへのログインに失敗しました。BOT_TOKENが正しいか、.envファイルを確認してください。")
    except Exception as e:
        logger.critical(f"ボット起動中に致命的なエラーが発生しました: {e}", exc_info=True)
    finally:
        logger.info("AI犬ボットの処理を終了します。お疲れ様でしたワン！")