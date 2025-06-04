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
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv
import sqlite3
import io # ファイル送信のサンプルで使用 (オプション)

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

# --- 設定クラス ---
@dataclass
class BotConfig:
    bot_token: str
    ollama_model_name: str
    ollama_api_url: str
    command_prefix: str = "!aidog "
    max_conversation_history: int = 5
    request_timeout: int = 180
    rate_limit_per_user: int = 5
    rate_limit_window: int = 60
    max_response_length: int = 1900
    admin_user_ids: List[int] = field(default_factory=list)
    conversation_db_path: str = "ai_dog_conversation_history.sqlite3"
    
    # Ollama パラメータ
    ollama_temperature: float = 0.7
    ollama_num_ctx: int = 4096
    ollama_top_p: float = 0.9
    ollama_repeat_penalty: float = 1.1
    progress_update_interval: int = 7

    # 天気機能用
    openweathermap_api_key: Optional[str] = None
    weather_default_city: str = "東京"

# --- 設定読み込みと検証 ---
def load_and_validate_config() -> BotConfig:
    bot_token_env = os.getenv("BOT_TOKEN")
    ollama_model_name_env = os.getenv("OLLAMA_MODEL_NAME")
    ollama_api_url_env = os.getenv("OLLAMA_API_URL")

    if not bot_token_env or not ollama_model_name_env or not ollama_api_url_env:
        missing = [var for var, val in [("BOT_TOKEN", bot_token_env), ("OLLAMA_MODEL_NAME", ollama_model_name_env), ("OLLAMA_API_URL", ollama_api_url_env)] if not val]
        logger.critical(f"致命的エラー: 必須の環境変数が設定されていません: {', '.join(missing)}")
        exit(1)

    admin_ids = []
    admin_user_ids_env = os.getenv("ADMIN_USER_IDS")
    if admin_user_ids_env:
        try:
            admin_ids = [int(x.strip()) for x in admin_user_ids_env.split(",") if x.strip().isdigit()]
            if not admin_ids and admin_user_ids_env: logger.warning("ADMIN_USER_IDS が設定されていますが、有効な数値のIDが含まれていません。")
        except ValueError: logger.warning("ADMIN_USER_IDS の形式が不正です。")
    
    config_instance = BotConfig(bot_token=bot_token_env, ollama_model_name=ollama_model_name_env, ollama_api_url=ollama_api_url_env, admin_user_ids=admin_ids)
    
    fields_to_load = [
        ("command_prefix", str), ("max_conversation_history", int), ("request_timeout", int),
        ("rate_limit_per_user", int), ("rate_limit_window", int), ("max_response_length", int),
        ("conversation_db_path", str), ("ollama_temperature", float), ("ollama_num_ctx", int),
        ("ollama_top_p", float), ("ollama_repeat_penalty", float), ("progress_update_interval", int),
        ("openweathermap_api_key", str), ("weather_default_city", str)
        # ("rss_feeds_file_path", str) # RSS機能を削除したのでこの行も削除
    ]
    for field_name, type_caster in fields_to_load:
        env_val = os.getenv(field_name.upper())
        if env_val is not None:
            try:
                setattr(config_instance, field_name, type_caster(env_val))
            except ValueError:
                logger.warning(f"環境変数 {field_name.upper()} の値「{env_val}」を型 {type_caster.__name__} に変換できませんでした。デフォルト値を使用します。")
        elif field_name == "openweathermap_api_key" and not config_instance.openweathermap_api_key:
            logger.warning("OPENWEATHERMAP_API_KEY が設定されていません。天気機能は利用できません。")

    return config_instance

# --- 会話履歴管理クラス (SQLite対応) ---
class ConversationManager:
    def __init__(self, max_history_for_context: int = 5, db_path: str = 'ai_dog_conversation_history.sqlite3'):
        self.max_history_for_context = max_history_for_context
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL )''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_timestamp ON conversation_log (user_id, timestamp)')
                conn.commit()
            logger.info(f"SQLite DB '{self.db_path}' 準備完了だワン。")
        except sqlite3.Error as e: logger.error(f"SQLite DB初期化エラー: {e}")

    def add_message(self, user_id: int, user_msg: str, bot_response: str):
        now_iso = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO conversation_log (user_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                               (str(user_id), now_iso, 'user', user_msg))
                cursor.execute("INSERT INTO conversation_log (user_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                               (str(user_id), datetime.now().isoformat(), 'assistant', bot_response))
                conn.commit()
        except sqlite3.Error as e: logger.error(f"会話ログDB保存エラー (User: {user_id}): {e}")

    def get_context(self, user_id: int) -> str:
        context_parts = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role, content FROM conversation_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                               (str(user_id), self.max_history_for_context * 2))
                rows = cursor.fetchall()
                if rows:
                    for row in reversed(rows):
                        role, content = row
                        context_parts.append(f"以前の{'ご主人様' if role == 'user' else 'AI犬'}の言葉: {content[:200]}")
                    logger.info(f"User: {user_id} のコンテキストをDBから {len(rows)//2} 往復分生成。")
        except sqlite3.Error as e:
            logger.error(f"コンテキスト取得SQLiteエラー (User: {user_id}): {e}")
            return "以前の会話を読み込めなかったワン..."
        return "\n".join(context_parts) if context_parts else "これが最初の会話だワン！"

    def clear_user_history(self, user_id: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM conversation_log WHERE user_id = ?", (str(user_id),))
                conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"User: {user_id} の会話履歴をDBから {deleted_count} 件削除。")
        except sqlite3.Error as e: logger.error(f"会話ログDB削除エラー (User: {user_id}): {e}")

# --- レート制限管理クラス (変更なし) ---
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests; self.window_seconds = window_seconds
        self.requests: Dict[int, deque] = defaultdict(deque)
    def is_rate_limited(self, user_id: int) -> Tuple[bool, int]:
        now = time.time(); user_reqs = self.requests[user_id]
        while user_reqs and now - user_reqs[0] > self.window_seconds: user_reqs.popleft()
        if len(user_reqs) >= self.max_requests:
            return True, int(self.window_seconds - (now - user_reqs[0]) + 1)
        user_reqs.append(now); return False, 0

# --- 統計管理クラス (変更なし) ---
class BotStats:
    def __init__(self):
        self.total_requests = 0; self.successful_requests = 0; self.failed_requests = 0
        self.total_response_time = 0.0; self.start_time = datetime.now()
    def record_request(self, success: bool, response_time: float):
        self.total_requests += 1
        if success: self.successful_requests += 1; self.total_response_time += response_time
        else: self.failed_requests += 1
    def get_stats(self) -> dict:
        up_delta = datetime.now()-self.start_time; up_str = str(timedelta(seconds=int(up_delta.total_seconds())))
        avg_rt = (self.total_response_time / self.successful_requests if self.successful_requests > 0 else 0)
        return {'uptime': up_str, 'total_requests': self.total_requests, 'successful_requests': self.successful_requests,
                'failed_requests': self.failed_requests, 'success_rate': f"{(self.successful_requests/self.total_requests*100):.1f}%" if self.total_requests > 0 else "N/A",
                'avg_response_time': f"{avg_rt:.2f}s"}

# --- AI犬ボットクラス ---
class AIDogBot(commands.Bot):
    def __init__(self, config_obj: BotConfig):
        intents = nextcord.Intents.default(); intents.message_content = True
        super().__init__(command_prefix=config_obj.command_prefix, intents=intents, help_command=None)
        self.config = config_obj
        self.conversation_manager = ConversationManager(self.config.max_conversation_history, db_path=self.config.conversation_db_path)
        self.rate_limiter = RateLimiter(self.config.rate_limit_per_user, self.config.rate_limit_window)
        self.stats = BotStats(); self.ollama_status = "初期化中..."
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
        # RSSフィード関連の属性は削除
        # self.rss_feeds: Dict[str, str] = {} 
        # self._load_rss_feeds() # 削除

    async def setup_hook(self):
        self.check_ollama_status_task.start()
        logger.info(f"AI犬「{self.user.name if self.user else 'AI犬'}」の初期化(setup_hook)完了だワン！")

    @tasks.loop(minutes=2)
    async def check_ollama_status_task(self):
        try:
            ollama_base_url = self.config.ollama_api_url.replace("/api/generate", "")
            if not ollama_base_url.endswith('/'): ollama_base_url += '/'
            async with requests.Session() as session: # type: ignore
                response = await asyncio.get_event_loop().run_in_executor(None, lambda: session.get(ollama_base_url, timeout=5))
            self.ollama_status = "オンライン" if response.status_code == 200 else f"エラー ({response.status_code})"
        except Exception: self.ollama_status = "オフライン"

    @check_ollama_status_task.before_loop
    async def before_check_ollama_status(self):
        await self.wait_until_ready()
        logger.info("Ollama状態チェックループを開始だワン。")

    # RSSフィード関連のメソッド (_load_rss_feeds, _save_rss_feeds) は削除

    async def ask_ai_inu(self, question: str, user_id: int) -> Tuple[str, bool, float]:
        start_time = time.time()
        try:
            context = self.conversation_manager.get_context(user_id)
            prompt = self.persona_prompt_template.format(context=context, question=question)
            payload = { "model": self.config.ollama_model_name, "prompt": prompt, "stream": False,
                        "options": { "temperature": self.config.ollama_temperature, "num_ctx": self.config.ollama_num_ctx,
                                     "top_p": self.config.ollama_top_p, "repeat_penalty": self.config.ollama_repeat_penalty } }
            headers = {"Content-Type": "application/json"}
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.post(self.config.ollama_api_url,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers=headers, timeout=self.config.request_timeout))
            response.raise_for_status()
            response_data = response.json()
            model_response = response_data.get("response", "").strip()
            if not model_response:
                logger.warning(f"モデル空応答 (User: {user_id}): {response_data}")
                return "AI犬、ちょっと言葉に詰まっちゃったワン…もう一度お願いできるかな？", False, time.time() - start_time
            cleanup_prefixes = ["応答:", "AI犬の応答:", "AI犬:", self.persona_prompt_template.split("{question}")[-1].split("応答:")[0]+"応答:"]
            for prefix in cleanup_prefixes:
                if model_response.lower().startswith(prefix.lower()): model_response = model_response[len(prefix):].strip()
            return model_response, True, time.time() - start_time
        except requests.exceptions.Timeout:
            logger.warning(f"Ollama APIタイムアウト (User: {user_id}, Q: {question[:30]})")
            return "うーん、考えるのに時間がかかりすぎちゃったワン！もう少し短い言葉で聞いてみてくれるかな？", False, time.time() - start_time
        except requests.exceptions.ConnectionError:
            logger.error(f"Ollama API接続エラー (User: {user_id})"); self.ollama_status = "オフライン (接続失敗)"
            return "わん！ご主人様、AI犬の脳みそと繋がらないみたい…。Ollamaサーバーの調子を見てほしいワン！", False, time.time() - start_time
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama APIリクエストエラー (User: {user_id}, Q: {question[:30]}): {e}")
            return f"ご主人様！モデル「{self.config.ollama_model_name}」とのお話に失敗しちゃったワン…（エラー: {type(e).__name__}）", False, time.time() - start_time
        except Exception as e:
            logger.error(f"ask_ai_inu予期せぬエラー (User: {user_id}, Q: {question[:30]}): {e}", exc_info=True)
            return "わわっ！AI犬、ちょっと混乱しちゃったみたい！ごめんなさい！", False, time.time() - start_time

    def sanitize_input(self, text: str) -> str:
        if len(text) > 2048: logger.warning(f"入力長超過: {len(text)} -> 2048"); text = text[:2048] + "...（長すぎなので省略だワン）"
        replacements = {"```": "`` ` ``", "<script": "&lt;script", "javascript:": "javascript&colon;"}
        role_indicators = ["system:", "user:", "assistant:", "<|im_start|>", "<|im_end|>", "<bos>", "<eos>", "<start_of_turn>", "<end_of_turn>", "model:"]
        for indicator in role_indicators: replacements[indicator] = f"{indicator.replace('<', '&lt;').replace('>', '&gt;')}"
        for pattern, replacement in replacements.items(): text = text.replace(pattern, replacement)
        return text.strip()

    async def handle_user_message(self, message: nextcord.Message, question: str):
        user_id = message.author.id
        attachment_info_parts = []
        processed_text_from_file = ""

        if message.attachments:
            for attachment in message.attachments:
                logger.info(f"User {message.author.name} からファイル添付: {attachment.filename} (Type: {attachment.content_type}, Size: {attachment.size} bytes)")
                attachment_info_parts.append(f"添付ファイル「{attachment.filename}」({attachment.size / 1024:.1f}KB)")
                if attachment.content_type and attachment.content_type.startswith('text/plain'):
                    try:
                        file_bytes = await attachment.read()
                        file_text = file_bytes.decode('utf-8')
                        processed_text_from_file += f"\n\n添付テキストファイル「{attachment.filename}」の内容(先頭500文字):\n{file_text[:500]}{'...' if len(file_text) > 500 else ''}\n"
                    except Exception as e: logger.error(f"テキストファイル「{attachment.filename}」読取失敗: {e}")
                elif attachment.content_type and attachment.content_type.startswith('image/'):
                    processed_text_from_file += f"\n\nわん！素敵な画像「{attachment.filename}」だね！AI犬はまだ目が見えないから、何が写っているか教えてほしいワン！\n"
        
        full_question_for_llm = f"{question}{processed_text_from_file}"
        sanitized_question = self.sanitize_input(full_question_for_llm)
                
        if not sanitized_question.strip() and not attachment_info_parts:
            if not (bot.user.mentioned_in(message) and not question.strip()):
                 await message.channel.send("わん？ご主人様、何かお話ししたいことがあるのかな？")
            return
        
        is_limited, wait_time = self.rate_limiter.is_rate_limited(user_id)
        if is_limited:
            await message.channel.send(f"{message.author.mention} AI犬、ちょっとお話疲れちゃったワン…🐾 {wait_time}秒待ってまた話しかけてね！"); return
        
        user_mention = f"{message.author.mention} " if not isinstance(message.channel, nextcord.DMChannel) else ""
        thinking_messages = ["AI犬がご主人様の言葉を一生懸命考えてるワン！🐕💭", "うーん、どんなお返事がいいかな？🤔", "最高の答えを探してるワン！✨", "もうちょっとでまとまるワン！待っててね！⏰"]
        initial_msg_content = user_mention
        if attachment_info_parts: initial_msg_content += " ".join(attachment_info_parts) + "について、"
        initial_msg_content += thinking_messages[0]
        processing_msg = await message.channel.send(initial_msg_content)
        logger.info(f"質問受付 - User: {message.author.name}({user_id}), Q(sanitized): {sanitized_question[:50]}")
        
        progress_task = None
        try:
            progress_task = asyncio.create_task(self.show_progress_async(processing_msg, user_mention, thinking_messages))
            if not sanitized_question.strip() and attachment_info_parts:
                reply_text = "ファイルをありがとうだワン！"
                if "画像" in processed_text_from_file: reply_text += " 何かこの画像について教えてほしいこととかあるワン？"
                elif "テキストファイル" in processed_text_from_file: reply_text += " このファイルについて、何かしてほしいことはあるワン？（例：要約して、など）"
                else: reply_text += " このファイルについて何か聞きたいことはあるワン？"
                success = True; response_time = 0.1
            else:
                reply_text, success, response_time = await self.ask_ai_inu(sanitized_question, user_id)

            if progress_task and not progress_task.done(): progress_task.cancel()
            self.stats.record_request(success, response_time)
            if len(reply_text) > self.config.max_response_length:
                reply_text = reply_text[:self.config.max_response_length] + "...わん！（お話が長すぎちゃった！ごめんね！）"
            await processing_msg.edit(content=f"{user_mention}{reply_text}")
            if success: self.conversation_manager.add_message(user_id, sanitized_question, reply_text)
            logger.info(f"応答完了 - Time: {response_time:.2f}s, Success: {success}, ReplyLen: {len(reply_text)}")
        except asyncio.CancelledError: logger.info("進捗タスクキャンセル (正常終了)")
        except Exception as e:
            logger.error(f"handle_user_messageエラー: {e}", exc_info=True)
            if progress_task and not progress_task.done(): progress_task.cancel()
            try: await processing_msg.edit(content=f"{user_mention}わわっ！AI犬、エラーになっちゃったワン！ごめんなさい！")
            except Exception as edit_e: logger.error(f"エラー時のメッセージ編集失敗: {edit_e}")

    async def show_progress_async(self, message: nextcord.Message, user_mention: str, thinking_messages: List[str]):
        try:
            idx = 0
            while True:
                idx = (idx + 1) % len(thinking_messages)
                try: await message.edit(content=f"{user_mention}{thinking_messages[idx]}")
                except nextcord.NotFound: logger.warning("進捗表示メッセージ消失。タスク停止。"); break
                except Exception as e_edit: logger.warning(f"進捗表示メッセージ編集失敗: {e_edit}")
                await asyncio.sleep(self.config.progress_update_interval)
        except asyncio.CancelledError: pass
        except Exception as e: logger.error(f"進捗タスクでエラー: {e}")

# --- グローバル設定とボットインスタンス ---
config = load_and_validate_config()
bot = AIDogBot(config)

# --- イベントハンドラー (グローバルスコープ) ---
@bot.event
async def on_ready():
    logger.info(f'AI犬「{bot.user.name}」(モデル: {bot.config.ollama_model_name}) が起動したワン！')
    print_lines = [f'      🐕 AI犬「{bot.user.name}」起動完了だワン！ 🐕', '=' * 60,
        f'🦴 モデル: {bot.config.ollama_model_name}', f'🔧 API URL: {bot.config.ollama_api_url}',
        f'🗣️ コマンドプレフィックス: 「{bot.config.command_prefix}」', f'⏱️ リクエストタイムアウト: {bot.config.request_timeout}秒',
        f'📚 会話履歴(コンテキスト用): {bot.config.max_conversation_history}往復', f'💾 会話ログDB: {bot.config.conversation_db_path}',
        f'⏳ レート制限: {bot.config.rate_limit_per_user}回 / {bot.config.rate_limit_window}秒',
        f'📏 最大応答長: {bot.config.max_response_length}文字', f'👑 管理者ID: {bot.config.admin_user_ids if bot.config.admin_user_ids else "未設定"}', '-' * 60]
    for line in print_lines: print(line)
    try:
        activity_name = "Gemma 2 2B JPNと遊んでるワン！"
        activity = nextcord.Game(name=activity_name)
        await bot.change_presence(status=nextcord.Status.online, activity=activity)
        logger.info(f"AI犬のステータスを「{activity_name}」に設定。"); print(f'🎮 ステータス: {activity_name}')
    except Exception as e: logger.error(f"ステータス設定エラー: {e}"); print(f'⚠️ ステータス設定エラー: {e}')
    print('-' * 60); print("ご主人様からのお話、いつでも待ってるワン！"); print('=' * 60)

@bot.event
async def on_message(message: nextcord.Message):
    if message.author.bot or message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, nextcord.DMChannel):
        raw_question = message.content
        if not isinstance(message.channel, nextcord.DMChannel):
            mention_parts = [f'<@{bot.user.id}>', f'<@!{bot.user.id}>']
            for part in mention_parts: raw_question = raw_question.replace(part, '')
        question = raw_question.strip()
        if not question and not isinstance(message.channel, nextcord.DMChannel) and bot.user.mentioned_in(message) and not message.attachments: # 添付ファイルもない場合
            await message.channel.send(f"{message.author.mention} わん！AI犬にご用かな？お気軽にお話ししてほしいワン！🐾"); return
        if question or message.attachments: # 質問があるか、添付ファイルがあれば処理
            await bot.handle_user_message(message, question)
    await bot.process_commands(message)

# --- コマンド定義 (グローバルスコープ) ---
@bot.command(name='stats', help="AI犬ボットの統計情報を表示しますだワン！")
async def show_stats_command(ctx: commands.Context):
    stats_data = bot.stats.get_stats()
    embed = nextcord.Embed(title="📊 AI犬ボット統計情報 📊", color=0x2ecc71, timestamp=datetime.now())
    if bot.user and bot.user.display_avatar: embed.set_thumbnail(url=bot.user.display_avatar.url)
    fields = [("🐕 ボット名", bot.user.name if bot.user else "AI犬", True), ("🧠 モデル", bot.config.ollama_model_name, True),
              ("🔌 Ollama", bot.ollama_status, True), ("⏱️ 稼働時間", stats_data['uptime'], True),
              ("🗣️ 総リクエスト", stats_data['total_requests'], True), ("📈 成功率", stats_data['success_rate'], True),
              ("✅ 成功", stats_data['successful_requests'], True), ("❌ 失敗", stats_data['failed_requests'], True),
              ("⏳ 平均応答", stats_data['avg_response_time'], True)]
    for name, value, inline in fields: embed.add_field(name=name, value=value, inline=inline)
    embed.set_footer(text="AI犬は今日も元気に稼働中だワン！")
    await ctx.send(embed=embed)

@bot.command(name='clear', help="AI犬との会話履歴をリセットするワン！")
async def clear_history_command(ctx: commands.Context):
    bot.conversation_manager.clear_user_history(ctx.author.id)
    await ctx.send(f"{ctx.author.mention} ご主人様との思い出（会話ログ）、リセットしたワン！✨ 新しいお話、いつでも楽しみにしてるワン！")

# --- 天気情報コマンド ---
@bot.command(name='weather', aliases=['天気', 'てんき'], help="指定都市の天気をお知らせ！ (例: !aidog weather 東京)")
async def weather_command(ctx: commands.Context, *, city: Optional[str] = None):
    if not bot.config.openweathermap_api_key:
        await ctx.send("ごめんなさいワン…お天気APIキーがないから、お天気をお知らせできないんだワン…。"); return

    target_city = city if city else bot.config.weather_default_city
    if not target_city:
        await ctx.send(f"どこのお天気が知りたいワン？ `{bot.config.command_prefix}weather 都市名` で教えて！"); return

    api_key = bot.config.openweathermap_api_key
    url = f"[http://api.openweathermap.org/data/2.5/weather?q=](http://api.openweathermap.org/data/2.5/weather?q=){target_city}&appid={api_key}&lang=ja&units=metric"
    processing_msg = await ctx.send(f"{target_city}のお天気を調べてるワン…🌦️")

    try:
        async with requests.Session() as session: # type: ignore
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: session.get(url, timeout=10))
        response.raise_for_status()
        data = response.json()

        if data.get("cod") != 200:
            await processing_msg.edit(content=f"「{target_city}」のお天気情報取得失敗 ({data.get('message', '不明')})。"); return

        city_name = data.get("name", target_city); desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]; t_min = data["main"]["temp_min"]; t_max = data["main"]["temp_max"]
        humidity = data["main"]["humidity"]; wind = data["wind"]["speed"]
        
        weather_text_for_llm = (f"今日の{city_name}の天気は「{desc}」、気温{temp}°C（最高{t_max}°C、最低{t_min}°C）、湿度は{humidity}%、風速{wind}mです。"
                                f"この天気について、AI犬として何か一言コメントしてください。例えば「お散歩に最高だワン！」とか「今日は傘がいるかも？」のように、天気に合わせた楽しくて役立つ短いコメントをお願いします。")
        
        weather_comment, success, _ = await bot.ask_ai_inu(weather_text_for_llm, ctx.author.id)

        embed = nextcord.Embed(title=f"🐕 {city_name}のお天気情報だワン！", color=0x7289da, timestamp=datetime.now())
        embed.add_field(name="天気", value=desc.capitalize(), inline=True)
        embed.add_field(name="気温", value=f"{temp:.1f}°C", inline=True)
        embed.add_field(name="最高/最低", value=f"{t_max:.1f}°C / {t_min:.1f}°C", inline=True)
        embed.add_field(name="湿度", value=f"{humidity}%", inline=True)
        embed.add_field(name="風速", value=f"{wind:.1f} m/s", inline=True)
        if success and weather_comment:
            embed.add_field(name="AI犬からの一言", value=weather_comment, inline=False)
        else:
            embed.add_field(name="AI犬からの一言", value="お出かけの参考にしてほしいワン！🐾 (コメント取得失敗)", inline=False)

        icon_id = data["weather"][0]["icon"]
        embed.set_thumbnail(url=f"[http://openweathermap.org/img/wn/](http://openweathermap.org/img/wn/){icon_id}@2x.png")
        embed.set_footer(text=f"情報取得元: OpenWeatherMap | {city_name}")
        await processing_msg.edit(content=None, embed=embed)

    except requests.exceptions.Timeout: await processing_msg.edit(content="お天気情報取得タイムアウトだワン…")
    except requests.exceptions.RequestException as e: logger.error(f"天気APIエラー({target_city}): {e}"); await processing_msg.edit(content="お天気情報取得エラーだワン…")
    except Exception as e: logger.error(f"天気処理エラー({target_city}): {e}", exc_info=True); await processing_msg.edit(content="お天気処理でエラーだワン！")

# --- ファイル送信コマンドの例 ---
@bot.command(name='bone', help="AI犬からホネの画像をもらうワン！🦴")
async def send_bone_picture(ctx: commands.Context):
    image_path = "bot_images/bone.png" # 事前に bot_images フォルダに bone.png を配置
    if os.path.exists(image_path):
        try:
            await ctx.send(f"{ctx.author.mention} ご主人様、ホネをどうぞだワン！🦴", file=nextcord.File(image_path))
            logger.info(f"画像「{image_path}」を {ctx.author.name} に送信。")
        except Exception as e:
            logger.error(f"画像送信エラー ({image_path}): {e}")
            await ctx.send("くぅーん、ホネを渡そうとしたけど失敗しちゃったワン…")
    else:
        logger.warning(f"画像ファイルが見つかりません: {image_path}")
        await ctx.send("わん！ホネの画像が見つからないワン…お腹すいちゃったのかな？")

@bot.command(name='textfile', help="AI犬からサンプルテキストファイルをもらうワン！")
async def send_text_file(ctx: commands.Context):
    file_content = "これはAI犬からご主人様への秘密のメッセージだワン！\nいつもありがとうだワン！大好きだワン！🐾"
    text_bytes = file_content.encode('utf-8')
    buffer = io.BytesIO(text_bytes) # io.BytesIO を使用 (import io が必要)
    await ctx.send(f"{ctx.author.mention} サンプルテキストファイルをどうぞだワン！📄", file=nextcord.File(buffer, filename="ai_inu_secret_message.txt"))
    logger.info(f"サンプルテキストファイルを {ctx.author.name} に送信。")

# --- help, reloadcfg, エラーハンドラ等 ---
@bot.command(name='help', help="AI犬ボットの使い方がわかるワン！") 
async def custom_help_command(ctx: commands.Context):
    embed = nextcord.Embed(title="🐾 AI犬ボット ヘルプだワン！ 🐾", color=0x3498db, timestamp=datetime.now())
    embed.description = f"ご主人様！AI犬の使い方はこんな感じだワン！\nボクのコマンドプレフィックスは「`{bot.config.command_prefix}`」だよ！"
    if bot.user and bot.user.display_avatar: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="💬 AI犬とお話しする方法", value=f"• AI犬にメンション (`@{bot.user.name if bot.user else 'AI犬'}`) + 聞きたいこと\n• AI犬にDMで聞きたいこと\n• メッセージにファイルを添付しても反応するワン！", inline=False)
    embed.add_field(name="🛠️ コマンド一覧", 
                    value=f"• `{bot.config.command_prefix}help` - このヘルプを表示するワン！\n"
                          f"• `{bot.config.command_prefix}stats` - AI犬の元気度（統計情報）をチェック！\n"
                          f"• `{bot.config.command_prefix}clear` - 前のお話を忘れて、新しいお話を始めるワン！\n"
                          f"• `{bot.config.command_prefix}weather <都市名>` - 指定した都市のお天気を教えるワン！\n"
                          f"• `{bot.config.command_prefix}bone` - AI犬からホネの画像をもらうワン！🦴\n"
                          f"• `{bot.config.command_prefix}textfile` - AI犬からサンプルテキストファイルをもらうワン！📄\n"
                          f"• `{bot.config.command_prefix}reloadcfg` - (管理者のみ) 設定を再読み込みするワン！", inline=False)
    embed.add_field(name="📝 ちょっとしたルールだワン！", value=f"• レート制限: {bot.config.rate_limit_per_user}回/{bot.config.rate_limit_window}秒\n"
                                                       f"• 会話履歴(コンテキスト): {bot.config.max_conversation_history}往復くらいまで記憶\n"
                                                       f"• タイムアウト: {bot.config.request_timeout}秒くらいで応答がなければ、もう一度試してみてワン！", inline=False)
    embed.set_footer(text="AI犬ともっともっと仲良くなろうワン！")
    await ctx.send(embed=embed)

@bot.command(name='reloadcfg', help="設定を再読み込みします（管理者専用）。")
@commands.is_owner() 
async def reload_config_command(ctx: commands.Context):
    try:
        logger.info(f"管理者 {ctx.author.name} ({ctx.author.id}) による設定再読み込み要求。")
        load_dotenv(override=True)
        global config 
        old_config_dict = config.__dict__.copy()
        new_config_instance = load_and_validate_config()
        config = new_config_instance 
        bot.config = config 
        bot.command_prefix = config.command_prefix
        bot.conversation_manager = ConversationManager(config.max_conversation_history, db_path=config.conversation_db_path)
        bot.rate_limiter = RateLimiter(config.rate_limit_per_user, config.rate_limit_window)
        
        changes = [f"{key}: `{old_config_dict.get(key)}` → `{getattr(config, key, None)}`" 
                   for key in old_config_dict if old_config_dict.get(key) != getattr(config, key, None)]
        if changes:
            change_summary = "\n".join(changes)
            embed = nextcord.Embed(title="⚙️ 設定再読み込み完了ワン！", description=f"AI犬が新しい設定でパワーアップ！🔋\n**変更点:**\n{change_summary}", color=0xffa500)
            await ctx.send(embed=embed); logger.info(f"設定更新完了。変更点: {', '.join(changes)}")
        else:
            await ctx.send("設定ファイルは現在の設定と同じだったワン！"); logger.info("設定再読み込み、変更なし。")
    except Exception as e:
        await ctx.send(f"設定再読み込み失敗…エラー: {str(e)}"); logger.error(f"設定再読み込みエラー: {e}", exc_info=True)

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"あれれ？「`{ctx.invoked_with}`」コマンド知らないワン… `{bot.config.command_prefix}help` で確認してね！")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"わん！「`{ctx.command.name}`」コマンドに必要なものが足りないみたい！ `{bot.config.command_prefix}help {ctx.command.name}` で使い方を確認してね！")
    elif isinstance(error, commands.NotOwner):
        await ctx.send("くぅーん...そのコマンドは特別なご主人様しか使えないんだワン...ごめんね！🐾")
    elif isinstance(error, commands.CommandInvokeError):
        logger.error(f"コマンド「{ctx.command.qualified_name if ctx.command else '不明'}」実行中エラー: {error.original}", exc_info=True)
        await ctx.send(f"わわっ！「`{ctx.command.qualified_name if ctx.command else '不明'}`」実行中に問題発生！もう一度試してみてね。")
    else:
        logger.error(f"未処理コマンドエラー: {error} (コマンド: {ctx.command.qualified_name if ctx.command else '不明'}, タイプ: {type(error)})", exc_info=True)
        await ctx.send("うーん、コマンドでよく分からないエラーが起きちゃったワン...ごめんなさい！")

# --- メイン実行 ---
if __name__ == '__main__':
    try:
        logger.info("AI犬ボットを起動準備中だワン...")
        bot.run(config.bot_token)
    except KeyboardInterrupt: logger.info("AI犬ボットがおやすみさせられました。またねだワン！💤")
    except nextcord.errors.LoginFailure: logger.critical("致命的エラー: Discordログイン失敗。BOT_TOKEN確認して！")
    except Exception as e: logger.critical(f"ボット起動中致命的エラー: {e}", exc_info=True)
    finally: logger.info("AI犬ボット処理終了。お疲れ様だワン！")