import nextcord
from nextcord.ext import commands
import xml.etree.ElementTree as ET
import random
import logging
from typing import List, Dict, Any, Optional
import asyncio
import difflib
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

NDL_API_BASE_URL = "https://iss.ndl.go.jp/api/opensearch"
NAMESPACES = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'openSearch': 'http://a9.com/-/spec/opensearchrss/1.0/'
}

def parse_xml_item(item: ET.Element) -> Dict[str, Any]:
    # (変更なし)
    return {
        'title': item.findtext('title', default='タイトル不明'),
        'link': item.findtext('link', default=''),
        'author': item.findtext('author', default='著者不明'),
        'pubDate': item.findtext('pubDate', default='出版日不明'),
        'description': item.findtext('description', default='説明なし'),
        'category': item.findtext('category', default='分類不明'),
        'publisher': item.findtext('dc:publisher', namespaces=NAMESPACES, default='出版社不明'),
        'thumbnail_url': item.find('rdfs:seeAlso', namespaces=NAMESPACES).get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource') if item.find('rdfs:seeAlso', namespaces=NAMESPACES) is not None else None
    }

def create_ndl_embed(item_data: Dict[str, Any], result_info: Optional[str] = None) -> nextcord.Embed:
    # (変更なし)
    embed = nextcord.Embed(title=item_data['title'], url=item_data['link'], color=0x0059A0)
    embed.add_field(name="著者", value=item_data['author'], inline=True)
    embed.add_field(name="出版社", value=item_data['publisher'], inline=True)
    embed.add_field(name="出版日", value=item_data['pubDate'], inline=True)
    if item_data['description'] != '説明なし':
        embed.add_field(name="説明", value=f"{item_data['description'][:200]}...", inline=False)
    if item_data['thumbnail_url']:
        embed.set_thumbnail(url=item_data['thumbnail_url'])
    footer_text = "Powered by 国立国会図書館サーチ"
    if result_info:
        footer_text = f"{result_info} | {footer_text}"
    embed.set_footer(text=footer_text)
    return embed

class NDLSearchView(nextcord.ui.View):
    # (変更なし)
    def __init__(self, ctx, items, total_results):
        super().__init__(timeout=180)
        self.ctx, self.items, self.total_results, self.current_page = ctx, items, total_results, 0
    async def show_page(self, interaction: nextcord.Interaction):
        result_info = f"{self.total_results}件中 {self.current_page + 1}件目"
        embed = create_ndl_embed(self.items[self.current_page], result_info)
        await interaction.response.edit_message(embed=embed, view=self)
    @nextcord.ui.button(label="◀️", style=nextcord.ButtonStyle.grey)
    async def prev_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.items)
        await self.show_page(interaction)
    @nextcord.ui.button(label="▶️", style=nextcord.ButtonStyle.grey)
    async def next_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.items)
        await self.show_page(interaction)

class QuizAnswerModal(nextcord.ui.Modal):
    # (変更なし)
    def __init__(self, cog, channel_id):
        super().__init__(title="書影クイズ 回答フォーム")
        self.cog, self.channel_id = cog, channel_id
        self.answer_input = nextcord.ui.TextInput(label="この本のタイトルは？", min_length=1, max_length=100)
        self.add_item(self.answer_input)
    async def callback(self, interaction: nextcord.Interaction):
        user_answer = self.answer_input.value
        quiz_data = self.cog.active_quizzes.pop(self.channel_id, None)
        if not quiz_data: return await interaction.response.send_message("クイズが見つかりませんでした。", ephemeral=True)
        correct_title = quiz_data['title']
        similarity = difflib.SequenceMatcher(None, user_answer, correct_title).ratio()
        msg = f"🎉 **正解だワン！**\n" if similarity > 0.7 else f"惜しいワン！不正解です…😢\n"
        await interaction.response.send_message(f"{msg}正解は「**{correct_title}**」でした！", ephemeral=False)

class NDLCog(commands.Cog, name="NDL検索"):
    def __init__(self, bot):
        self.bot = bot
        self.active_quizzes: Dict[int, Dict[str, Any]] = {}
        self.random_keywords = ["科学", "歴史", "文学", "芸術", "宇宙", "プログラミング", "経済", "写真"]
        self.quiz_keywords = ["写真集", "絵本", "画集", "漫画", "雑誌"]

    async def _search_ndl(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # (変更なし)
        try:
            logger.info(f"NDL API Request: {params}")
            async with self.bot.http_session.get(NDL_API_BASE_URL, params=params) as response:
                response.raise_for_status()
                xml_text = await response.text()
                if not xml_text: return None
                root = ET.fromstring(xml_text)
                total_results_elem = root.find('channel/openSearch:totalResults', namespaces=NAMESPACES)
                if total_results_elem is None or not total_results_elem.text.isdigit():
                    return {"total": 0, "items": []}
                return { "total": int(total_results_elem.text), "items": [parse_xml_item(item) for item in root.findall('channel/item')] }
        except (aiohttp.ClientError, ET.ParseError) as e:
            logger.error(f"NDL API Search Error: {e}", exc_info=True)
            return None

    @commands.group(name="ndl", invoke_without_command=True)
    async def ndl(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @ndl.command(name="search", aliases=["s", "検索"])
    async def search(self, ctx: commands.Context, *, keyword: str):
        # (変更なし)
        await ctx.send(f"`{keyword}` で資料を探してくるワン！📖")
        result = await self._search_ndl({"any": keyword, "cnt": 10})
        if result is None: return await ctx.send("資料の検索中にエラーが…")
        if not result['items']: return await ctx.send("お探しの資料は見つからなかったワン…")
        view = NDLSearchView(ctx, result['items'], result['total'])
        result_info = f"{result['total']}件中 1件目"
        embed = create_ndl_embed(result['items'][0], result_info)
        await ctx.send(embed=embed, view=view)

    @ndl.command(name="random", aliases=["r", "おすすめ"])
    async def random(self, ctx: commands.Context):
        # (変更なし)
        await ctx.send("ご主人様のために、素敵な本を1冊選んでくるワン！")
        try:
            keyword = random.choice(self.random_keywords)
            logger.info(f"ランダム推薦のキーワードとして '{keyword}' を選択しました。")
            params = {"any": keyword, "mediatype": 1, "cnt": 1, "sortkey": "d"}
            result = await self._search_ndl(params)
            if result is None or not result.get('items'):
                return await ctx.send("うーん、ピンとくる本が見つからなかったワン…もう一度試してみてね。")
            item = result['items'][0]
            result_info = f"キーワード「{keyword}」の検索結果より"
            embed = create_ndl_embed(item, result_info)
            await ctx.send(content="今日の一冊はこれだワン！", embed=embed)
        except Exception as e:
            logger.error(f"ランダム推薦コマンドで予期せぬエラー: {e}", exc_info=True)
            await ctx.send("ランダムな本の選出中に、予期せぬエラーが発生しました。")

    @ndl.command(name="quiz", aliases=["q", "クイズ"])
    async def quiz(self, ctx: commands.Context):
        # (変更なし)
        if ctx.channel.id in self.active_quizzes:
            return await ctx.send("このチャンネルではまだクイズの回答待ちだワン！")
        await ctx.send("書影クイズの準備中… 面白そうな表紙を探してくるワン！")
        for _ in range(5):
            keyword = random.choice(self.quiz_keywords)
            params = {"any": keyword, "mediatype": random.choice(["1", "7"]), "cnt": 50}
            search_result = await self._search_ndl(params)
            if search_result and search_result.get('items'):
                valid_items = [item for item in search_result['items'] if item.get('thumbnail_url')]
                if valid_items:
                    quiz_item = random.choice(valid_items)
                    self.active_quizzes[ctx.channel.id] = quiz_item
                    view = nextcord.ui.View(timeout=60.0)
                    answer_button = nextcord.ui.Button(label="回答する", style=nextcord.ButtonStyle.green)
                    async def btn_callback(interaction: nextcord.Interaction):
                        await interaction.response.send_modal(QuizAnswerModal(self, interaction.channel.id))
                    answer_button.callback = btn_callback
                    view.add_item(answer_button)
                    def on_timeout_func():
                        if self.active_quizzes.pop(ctx.channel.id, None):
                            asyncio.create_task(ctx.send(f"時間切れだワン！正解は「**{quiz_item['title']}**」でした！"))
                    view.on_timeout = on_timeout_func
                    embed = nextcord.Embed(title="この本のタイトルは何だワン？", color=0xFFC107)
                    embed.set_image(url=quiz_item['thumbnail_url'])
                    await ctx.send(embed=embed, view=view)
                    return
        await ctx.send("クイズを出題できる本が見つからなかったワン…ごめんね。")

    @ndl.command(name="history", aliases=["h", "歴史"])
    async def history(self, ctx: commands.Context, *, keyword: str):
        # (変更なし)
        await ctx.send(f"`{keyword}` に関連する歴史的資料を探してくるワン！📜")
        params = {"any": keyword, "mediatype": 7, "cnt": 10}
        result = await self._search_ndl(params)
        if result is None: return await ctx.send("歴史資料の検索中にエラーが…")
        if not result['items']: return await ctx.send("お探しの歴史的資料は見つからなかったワン…")
        view = NDLSearchView(ctx, result['items'], result['total'])
        result_info = f"{result['total']}件中 1件目"
        embed = create_ndl_embed(result['items'][0], result_info)
        await ctx.send(embed=embed, view=view)

    # ★★★【改善版】mapコマンド ★★★
    @ndl.command(name="map", aliases=["m", "地図"])
    async def map_search(self, ctx: commands.Context, *, keyword: str):
        """キーワードに関連する地図や絵図を、より広い範囲から検索します。"""
        await ctx.send(f"`{keyword}` に関連する地図や絵図を探してくるワン！🗺️")
        
        # ユーザーのキーワードに「地図 OR 絵図」を追加して検索精度を向上
        search_keyword = f"{keyword} 地図 OR 絵図"
        
        # 検索対象を「地図(5)」と「デジタル資料(7)」の両方に広げる
        params = {"any": search_keyword, "mediatype": ["5", "7"], "cnt": 10} 
        
        result = await self._search_ndl(params)
        if result is None: 
            return await ctx.send("地図の検索中にエラーが起きてしまったワン…")
        if not result['items']: 
            return await ctx.send(f"ごめんね、`{keyword}` に関連する地図や絵図は見つからなかったワン…")
            
        view = NDLSearchView(ctx, result['items'], result['total'])
        result_info = f"{result['total']}件中 1件目"
        embed = create_ndl_embed(result['items'][0], result_info)
        await ctx.send(embed=embed, view=view)

def setup(bot):
    bot.add_cog(NDLCog(bot))