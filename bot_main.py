import nextcord
from nextcord.ext import commands, tasks
import asyncio
import time
import json
import logging
import os
import aiohttp
from urllib.parse import urljoin
from datetime import datetime
from typing import Optional, Tuple

from config import BotConfig, load_and_validate_config
from utils.conversation_manager import ConversationManager
from utils.bot_utils import RateLimiter, BotStats

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_dog_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

config = load_and_validate_config()
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config.command_prefix, intents=intents, help_command=None)

bot.config = config
bot.conversation_manager = ConversationManager(config.max_conversation_history, db_path=config.conversation_db_path)
bot.rate_limiter = RateLimiter(config.rate_limit_per_user, config.rate_limit_window)
bot.stats = BotStats()
bot.http_session: Optional[aiohttp.ClientSession] = None
bot.ollama_status = "初期化中..."

bot.persona_prompt_template = """
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

async def set_idle_status():
    model_name = bot.config.ollama_model_name
    activity = nextcord.Game(name=model_name)
    await bot.change_presence(status=nextcord.Status.online, activity=activity)
    logger.info(f"ステータスをアイドルに変更: {model_name}")

async def set_busy_status():
    activity = nextcord.Game(name="思考中... 🧠")
    await bot.change_presence(status=nextcord.Status.online, activity=activity)
    logger.info("ステータスをビジーに変更")

async def ask_ai_inu(question: str, user_id: int) -> Tuple[str, bool, float]:
    start_time = time.time()
    context = bot.conversation_manager.get_context(user_id)
    prompt = bot.persona_prompt_template.format(context=context, question=question)
    payload = {"model": bot.config.ollama_model_name, "prompt": prompt, "stream": False, "options": {"temperature": bot.config.ollama_temperature, "num_ctx": bot.config.ollama_num_ctx, "top_p": bot.config.ollama_top_p, "repeat_penalty": bot.config.ollama_repeat_penalty}}
    try:
        async with bot.http_session.post(bot.config.ollama_api_url, json=payload, timeout=bot.config.request_timeout) as response:
            response.raise_for_status()
            response_data = await response.json()
        model_response = response_data.get("response", "").strip()
        if not model_response:
            logger.warning(f"モデル空応答 (User: {user_id}): {response_data}"); return "AI犬、ちょっと言葉に詰まっちゃったワン…", False, time.time() - start_time
        cleanup_prefixes = ["応答:", "AI犬の応答:", "AI犬:", "AI犬として、上記全てを踏まえた上で、最高の応答をしてくださいだワン！\n応答:"]
        for prefix in cleanup_prefixes:
            if model_response.lower().startswith(prefix.lower()): model_response = model_response[len(prefix):].strip()
        return model_response, True, time.time() - start_time
    except asyncio.TimeoutError: logger.warning(f"Ollama APIタイムアウト (User: {user_id})"); return "うーん、考えるのに時間がかかりすぎちゃったワン！", False, time.time() - start_time
    except aiohttp.ClientError as e: logger.error(f"Ollama API接続/リクエストエラー (User: {user_id}): {e}", exc_info=True); bot.ollama_status = "オフライン"; return "わん！ご主人様、AI犬の脳みそと繋がらないみたい…。", False, time.time() - start_time
    except Exception as e: logger.error(f"ask_ai_inu予期せぬエラー (User: {user_id}): {e}", exc_info=True); return "わわっ！AI犬、ちょっと混乱しちゃったみたい！", False, time.time() - start_time

def sanitize_input(text: str) -> str:
    if len(text) > 2048: logger.warning(f"入力長超過: {len(text)} -> 2048"); text = text[:2048] + "...（省略）"
    replacements = {"```": "`` ` ``", "<script": "&lt;script", "javascript:": "javascript&colon;"}
    role_indicators = ["system:", "user:", "assistant:", "<|im_start|>", "<|im_end|>", "<bos>", "<eos>", "<start_of_turn>", "<end_of_turn>", "model:"]
    for indicator in role_indicators: replacements[indicator] = f"{indicator.replace('<', '&lt;').replace('>', '&gt;')}"
    for pattern, replacement in replacements.items(): text = text.replace(pattern, replacement)
    return text.strip()

@bot.event
async def on_ready():
    bot.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=bot.config.request_timeout))
    await set_idle_status()
    check_ollama_status_task.start()
    logger.info(f'AI犬「{bot.user.name}」(モデル: {bot.config.ollama_model_name}) が起動したワン！')
    print_lines = [
        f'{"="*60}', f'      🐕 AI犬「{bot.user.name}」起動完了だワン！ 🐕', f'{"="*60}',
        f'  - モデル: {bot.config.ollama_model_name}', f'  - API URL: {bot.config.ollama_api_url}',
        f'  - コマンドプレフィックス: 「{bot.config.command_prefix}」', f'  - 管理者ID: {bot.config.admin_user_ids if bot.config.admin_user_ids else "未設定"}', f'{"-"*60}'
    ]
    print('\n'.join(print_lines))
    print("ご主人様からのお話、いつでも待ってるワン！\n" + "="*60)

@bot.event
async def on_message(message: nextcord.Message):
    if message.author.bot or message.author == bot.user: return
    await bot.process_commands(message)
    if message.content.startswith(bot.config.command_prefix): return

    if bot.user.mentioned_in(message) or isinstance(message.channel, nextcord.DMChannel):
        is_limited, wait_time = bot.rate_limiter.is_rate_limited(message.author.id)
        if is_limited:
            await message.channel.send(f"{message.author.mention} ちょっとお話疲れちゃった… {wait_time}秒待ってね！"); return
        
        raw_question = message.content
        if not isinstance(message.channel, nextcord.DMChannel):
            mention_parts = [f'<@{bot.user.id}>', f'<@!{bot.user.id}>']
            for part in mention_parts: raw_question = raw_question.replace(part, '')
        question = raw_question.strip()

        if not question and not message.attachments:
            if bot.user.mentioned_in(message): await message.channel.send(f"{message.author.mention} わん！AI犬にご用かな？")
            return

        try:
            await set_busy_status()
            sanitized_question = sanitize_input(question)
            async with message.channel.typing():
                logger.info(f"質問受付 - User: {message.author.name}, Q: {sanitized_question[:50]}")
                reply_text, success, response_time = await ask_ai_inu(sanitized_question, message.author.id)
                bot.stats.record_request(success, response_time)
                if success: bot.conversation_manager.add_message(message.author.id, sanitized_question, reply_text)
                if len(reply_text) > bot.config.max_response_length: reply_text = reply_text[:bot.config.max_response_length] + "…（省略）"
                user_mention = f"{message.author.mention} " if not isinstance(message.channel, nextcord.DMChannel) else ""
                await message.channel.send(f"{user_mention}{reply_text}")
                logger.info(f"応答完了 - Time: {response_time:.2f}s, Success: {success}")
        finally:
            await set_idle_status()

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound): pass
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send(f"わん！「`{ctx.command.name}`」に必要なものが足りないみたい！")
    elif isinstance(error, (commands.NotOwner, commands.CheckFailure)): await ctx.send("くぅーん...そのコマンドは特別なご主人様しか使えないんだワン...🐾")
    elif isinstance(error, commands.CommandInvokeError):
        logger.error(f"コマンド「{ctx.command.qualified_name}」実行中エラー: {error.original}", exc_info=True)
        await ctx.send(f"わわっ！「`{ctx.command.qualified_name}`」実行中に問題発生！")
    else:
        logger.error(f"未処理コマンドエラー: {error}", exc_info=True)
        await ctx.send("うーん、コマンドでよく分からないエラーが…")

@tasks.loop(minutes=2)
async def check_ollama_status_task():
    if not bot.http_session: return
    try:
        ollama_base_url = urljoin(bot.config.ollama_api_url, '.')
        async with bot.http_session.get(ollama_base_url, timeout=5) as response:
            bot.ollama_status = "オンライン" if response.status == 200 else f"エラー ({response.status})"
    except (aiohttp.ClientError, asyncio.TimeoutError):
        bot.ollama_status = "オフライン"

logger.info("--- Cogの読み込みを開始します... ---")
for filename in os.listdir('./cogs'):
    if filename.endswith('.py') and not filename.startswith('__'):
        extension = f'cogs.{filename[:-3]}'
        try:
            bot.load_extension(extension)
            logger.info(f"SUCCESS: Cog '{extension}' の読み込みに成功しました。")
        except Exception as e:
            logger.error(f"FAILED: Cog '{extension}' の読み込みに失敗しました。", exc_info=e)

if __name__ == '__main__':
    try:
        logger.info("AI犬ボットを起動準備中だワン...")
        bot.run(config.bot_token)
    except Exception as e:
        logger.critical(f"ボット起動中に致命的なエラーが発生しました: {e}", exc_info=True)