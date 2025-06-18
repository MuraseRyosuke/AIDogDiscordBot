# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」の国立国会図書館サーチ連携機能（Cog）。

書籍や歴史資料の検索、書影を使ったクイズ機能などを提供します。
"""
# --- 標準ライブラリのインポート ---
import asyncio
import difflib
import logging
import random
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# --- サードパーティライブラリのインポート ---
import aiohttp
import nextcord
from nextcord.ext import commands

# 型ヒントのために 'AIDogBot' クラスをインポートする（循環参照を避ける）
if TYPE_CHECKING:
    from bot_main import AIDogBot

logger = logging.getLogger(__name__)

# --- モジュールレベルの定数・ヘルパー関数 ---
NDL_API_BASE_URL = "https://iss.ndl.go.jp/api/opensearch"
NAMESPACES = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'openSearch': 'http://a9.com/-/spec/opensearchrss/1.0/'
}

def parse_xml_item(item: ET.Element) -> Dict[str, Any]:
    """XMLのitem要素をパースして辞書に変換する。"""
    thumbnail_elem = item.find('rdfs:seeAlso', namespaces=NAMESPACES)
    thumbnail_url = thumbnail_elem.get(f"{{{NAMESPACES['rdf']}}}resource") if thumbnail_elem is not None else None

    return {
        'title': item.findtext('title', default='タイトル不明'),
        'link': item.findtext('link', default=''),
        'author': item.findtext('author', default='著者不明'),
        'pubDate': item.findtext('pubDate', default='出版日不明'),
        'description': item.findtext('description', default='説明なし'),
        'publisher': item.findtext('dc:publisher', namespaces=NAMESPACES, default='出版社不明'),
        'thumbnail_url': thumbnail_url
    }

def create_ndl_embed(item_data: Dict[str, Any], result_info: Optional[str] = None) -> nextcord.Embed:
    """資料データからEmbedオブジェクトを作成する。"""
    embed = nextcord.Embed(title=item_data['title'], url=item_data.get('link'), color=0x0059A0)
    embed.add_field(name="著者", value=item_data['author'], inline=True)
    embed.add_field(name="出版社", value=item_data['publisher'], inline=True)
    embed.add_field(name="出版日", value=item_data['pubDate'], inline=True)
    if desc := item_data.get('description', '説明なし'):
        embed.add_field(name="説明", value=f"{desc[:200]}..." if len(desc) > 200 else desc, inline=False)
    if thumbnail := item_data.get('thumbnail_url'):
        embed.set_thumbnail(url=thumbnail)

    footer_text = "Powered by 国立国会図書館サーチ"
    if result_info:
        footer_text = f"{result_info} | {footer_text}"
    embed.set_footer(text=footer_text)
    return embed


# --- UIコンポーネント ---
class NDLSearchView(nextcord.ui.View):
    """NDL検索結果をページネーションで表示するためのView。"""
    def __init__(self, items: List[Dict[str, Any]], total_results: int):
        super().__init__(timeout=180.0)
        self.items = items
        self.total_results = total_results
        self.current_page = 0

    async def show_page(self, interaction: nextcord.Interaction):
        """指定されたページのEmbedを表示する。"""
        result_info = f"{self.total_results}件中 {self.current_page + 1}件目"
        embed = create_ndl_embed(self.items[self.current_page], result_info)
        await interaction.response.edit_message(embed=embed, view=self)

    @nextcord.ui.button(label="◀️ 前へ", style=nextcord.ButtonStyle.grey)
    async def prev_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.items)
        await self.show_page(interaction)

    @nextcord.ui.button(label="▶️ 次へ", style=nextcord.ButtonStyle.grey)
    async def next_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.items)
        await self.show_page(interaction)


class QuizAnswerModal(nextcord.ui.Modal):
    """書影クイズの回答を入力するためのModal。"""
    def __init__(self, cog: 'NDLCog', correct_title: str):
        super().__init__(title="書影クイズ 回答フォーム")
        self.cog = cog
        self.correct_title = correct_title
        self.answer_input = nextcord.ui.TextInput(label="この本のタイトルは？", min_length=1, max_length=100)
        self.add_item(self.answer_input)

    async def callback(self, interaction: nextcord.Interaction):
        user_answer = self.answer_input.value
        # 類似度を計算して正誤判定
        similarity = difflib.SequenceMatcher(None, user_answer.lower(), self.correct_title.lower()).ratio()
        
        if similarity > 0.7:
            await interaction.response.send_message(f"🎉 **正解だワン！**\n正解は「**{self.correct_title}**」でした！")
        else:
            await interaction.response.send_message(f"惜しいワン！不正解です…😢\n正解は「**{self.correct_title}**」でした！")
        # 回答されたらアクティブなクイズリストから削除
        self.cog.active_quizzes.pop(interaction.channel.id, None)


class QuizView(nextcord.ui.View):
    """クイズの「回答する」ボタンとタイムアウト処理を持つView。"""
    def __init__(self, cog: 'NDLCog'):
        super().__init__(timeout=cog.QUIZ_TIMEOUT)
        self.cog = cog

    @nextcord.ui.button(label="回答する", style=nextcord.ButtonStyle.green)
    async def answer_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        quiz_data = self.cog.active_quizzes.get(interaction.channel.id)
        if not quiz_data:
            await interaction.response.send_message("このクイズはもう終わっちゃったみたいだワン！", ephemeral=True)
            return
        await interaction.response.send_modal(QuizAnswerModal(self.cog, quiz_data['title']))

    async def on_timeout(self):
        # Viewのon_timeoutはinteractionを持たないため、自身でチャンネルIDを保持する必要がある
        # 今回はCogのactive_quizzesから探すが、本来はView初期化時にchannelを渡すのが堅牢
        # タイムアウトしたクイズを探して削除し、メッセージを送信
        for channel_id, quiz_data in list(self.cog.active_quizzes.items()):
            # このViewが関連するクイズかどうかの厳密な判定は難しいが、ここではタイムアウトしたものを処理
            if self.cog.active_quizzes.pop(channel_id, None):
                 try:
                    channel = self.cog.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(f"時間切れだワン！正解は「**{quiz_data['title']}**」でした！")
                 except Exception as e:
                    logger.error(f"クイズのタイムアウトメッセージ送信に失敗: {e}")


# --- Cog本体 ---
class NDLCog(commands.Cog, name="NDL検索"):
    """国立国会図書館サーチ連携機能"""
    
    # --- クラス定数 ---
    QUIZ_RETRY_COUNT = 5
    QUIZ_TIMEOUT = 60.0
    
    def __init__(self, bot: 'AIDogBot'):
        self.bot = bot
        self.active_quizzes: Dict[int, Dict[str, Any]] = {}
        self.random_keywords = ["科学", "歴史", "文学", "芸術", "宇宙", "プログラミング", "経済", "写真"]
        self.quiz_keywords = ["写真集", "絵本", "画集", "漫画", "雑誌"]

    async def _search_ndl(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """NDL APIにリクエストを送信し、パースした結果を返す。"""
        try:
            logger.info(f"NDL API Request: {params}")
            async with self.bot.http_session.get(NDL_API_BASE_URL, params=params) as response:
                response.raise_for_status()
                xml_text = await response.text()
                if not xml_text:
                    return None
                
                root = ET.fromstring(xml_text)
                total_results_elem = root.find('channel/openSearch:totalResults', namespaces=NAMESPACES)
                total = int(total_results_elem.text) if total_results_elem is not None and total_results_elem.text.isdigit() else 0
                items = [parse_xml_item(item) for item in root.findall('channel/item')]
                return {"total": total, "items": items}
        except (aiohttp.ClientError, ET.ParseError) as e:
            logger.error(f"NDL API Search Error: {e}", exc_info=True)
            return None

    async def _execute_search(self, ctx: commands.Context, params: Dict[str, Any], not_found_msg: str):
        """検索処理を実行し、結果をページネーションで表示する共通メソッド。"""
        result = await self._search_ndl(params)
        if result is None:
            await ctx.send("資料の検索中にエラーが起きてしまったワン…")
            return
        if not result.get('items'):
            await ctx.send(not_found_msg)
            return
            
        view = NDLSearchView(result['items'], result['total'])
        result_info = f"{result['total']}件中 1件目"
        embed = create_ndl_embed(result['items'][0], result_info)
        await ctx.send(embed=embed, view=view)

    # --- コマンドグループ ---
    @commands.group(name="ndl", invoke_without_command=True, help="国立国会図書館の資料を検索するワン！")
    async def ndl(self, ctx: commands.Context):
        """'ndl'コマンドがサブコマンドなしで呼ばれた場合にヘルプを表示する。"""
        await ctx.send_help(ctx.command)

    @ndl.command(name="search", aliases=["s"], help="キーワードで資料を検索します。")
    async def search(self, ctx: commands.Context, *, keyword: str):
        await ctx.send(f"`{keyword}` で資料を探してくるワン！📖")
        params = {"any": keyword, "cnt": 10}
        not_found_msg = "お探しの資料は見つからなかったワン…"
        await self._execute_search(ctx, params, not_found_msg)

    @ndl.command(name="history", aliases=["h"], help="キーワードで歴史的資料を検索します。")
    async def history(self, ctx: commands.Context, *, keyword: str):
        await ctx.send(f"`{keyword}` に関連する歴史的資料を探してくるワン！📜")
        params = {"any": keyword, "mediatype": 7, "cnt": 10}
        not_found_msg = "お探しの歴史的資料は見つからなかったワン…"
        await self._execute_search(ctx, params, not_found_msg)

    @ndl.command(name="map", aliases=["m"], help="キーワードで地図資料を検索します。")
    async def map_search(self, ctx: commands.Context, *, keyword: str):
        await ctx.send(f"`{keyword}` に関連する地図や絵図を探してくるワン！🗺️")
        search_keyword = f"{keyword} 地図 OR 絵図"
        params = {"any": search_keyword, "mediatype": ["5", "7"], "cnt": 10}
        not_found_msg = f"ごめんね、`{keyword}` に関連する地図や絵図は見つからなかったワン…"
        await self._execute_search(ctx, params, not_found_msg)

    @ndl.command(name="random", aliases=["r"], help="AI犬おすすめの本をランダムで紹介します。")
    async def random(self, ctx: commands.Context):
        await ctx.send("ご主人様のために、素敵な本を1冊選んでくるワン！")
        try:
            keyword = random.choice(self.random_keywords)
            logger.info(f"ランダム推薦のキーワードとして '{keyword}' を選択しました。")
            params = {"any": keyword, "mediatype": 1, "cnt": 1}
            result = await self._search_ndl(params)
            
            if not result or not result.get('items'):
                await ctx.send("うーん、ピンとくる本が見つからなかったワン…もう一度試してみてね。")
                return
                
            item = result['items'][0]
            embed = create_ndl_embed(item, f"キーワード「{keyword}」より")
            await ctx.send(content="今日の一冊はこれだワン！", embed=embed)
        except Exception as e:
            logger.error(f"ランダム推薦コマンドで予期せぬエラー: {e}", exc_info=True)
            await ctx.send("ランダムな本の選出中に、予期せぬエラーが発生しました。")

    @ndl.command(name="quiz", aliases=["q"], help="書影を見て本のタイトルを当てるクイズです。")
    async def quiz(self, ctx: commands.Context):
        if ctx.channel.id in self.active_quizzes:
            await ctx.send("このチャンネルではまだクイズの回答待ちだワン！")
            return
            
        await ctx.send("書影クイズの準備中… 面白そうな表紙を探してくるワン！")
        
        # クイズに適したアイテム（書影あり）を探す
        quiz_item = None
        for _ in range(self.QUIZ_RETRY_COUNT):
            keyword = random.choice(self.quiz_keywords)
            params = {"any": keyword, "mediatype": "1", "cnt": 50}
            result = await self._search_ndl(params)
            if result and result.get('items'):
                valid_items = [item for item in result['items'] if item.get('thumbnail_url')]
                if valid_items:
                    quiz_item = random.choice(valid_items)
                    break # アイテムが見つかったらループを抜ける
        
        if not quiz_item:
            await ctx.send("クイズを出題できる本が見つからなかったワン…ごめんね。")
            return

        # クイズを出題
        self.active_quizzes[ctx.channel.id] = quiz_item
        view = QuizView(self)
        embed = nextcord.Embed(title="この本のタイトルは何だワン？", color=nextcord.Color.gold())
        embed.set_image(url=quiz_item['thumbnail_url'])
        await ctx.send(embed=embed, view=view)


def setup(bot: 'AIDogBot'):
    """CogをBotに登録するためのセットアップ関数"""
    bot.add_cog(NDLCog(bot))