# cogs/gourmet.py
import nextcord
from nextcord.ext import commands
import random
import logging
from typing import Optional
import aiohttp # エラーハンドリング用にインポート

logger = logging.getLogger(__name__)

API_BASE_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"

class GourmetCog(commands.Cog, name="グルメ検索"):
    """ホットペッパーグルメAPIを使ってお店の情報を検索するCog"""
    def __init__(self, bot):
        self.bot = bot

    def create_shop_embed(self, shop_data: dict, result_info: Optional[str] = None) -> nextcord.Embed:
        """お店のデータからEmbedオブジェクトを作成するヘルパー関数"""
        embed = nextcord.Embed(
            title=shop_data.get('name', '名称不明'),
            url=shop_data.get('urls', {}).get('pc', None),
            description=shop_data.get('catch', ''),
            color=0xF04B00 # ホットペッパーのオレンジ色
        )
        if shop_data.get('logo_image'):
            embed.set_thumbnail(url=shop_data['logo_image'])
        
        embed.add_field(name="ジャンル", value=shop_data.get('genre', {}).get('name', 'N/A'), inline=True)
        embed.add_field(name="アクセス", value=shop_data.get('mobile_access', 'N/A'), inline=False)
        embed.add_field(name="住所", value=shop_data.get('address', 'N/A'), inline=False)
        embed.add_field(name="営業時間", value=shop_data.get('open', 'N/A'), inline=False)
        
        if shop_data.get('photo', {}).get('pc', {}).get('l'):
            embed.set_image(url=shop_data['photo']['pc']['l'])
        
        footer_text = "Powered by ホットペッパー Webサービス"
        if result_info:
            footer_text = f"{result_info} | {footer_text}"
        embed.set_footer(text=footer_text)
        return embed

    @commands.command(name='gourmet', aliases=['グルメ', 'ごはん'], help="指定キーワードでお店を検索します (例: !aidog gourmet 札幌駅 ラーメン)")
    async def gourmet_search(self, ctx: commands.Context, *, keyword: str):
        if not self.bot.config.hotpepper_api_key:
            return await ctx.send("ごめんなさいワン… グルメAPIキーがないから、お店を探せないんだワン…。")

        await ctx.send(f"`{keyword}` でお店を探してるワン… ちょっと待っててね！🍜")

        params = {"key": self.bot.config.hotpepper_api_key, "keyword": keyword, "count": 3, "format": "json"}
        try:
            async with self.bot.http_session.get(API_BASE_URL, params=params) as response:
                response.raise_for_status()
                # ★★★ 修正点1 ★★★
                # サーバーの応答タイプが特殊なため、text/javascriptでもJSONとして読み込むように指定
                data = await response.json(content_type='text/javascript;charset=utf-8')

            results = data.get('results', {})
            shops = results.get('shop', [])

            if not shops:
                return await ctx.send(f"`{keyword}` に合うお店は見つからなかったワン… ごめんね！")
            
            total_found = int(results.get('results_available', 0))
            await ctx.send(f"`{keyword}` に合うお店が {total_found} 件見つかったワン！トップ{len(shops)}件を紹介するね！")
            for i, shop in enumerate(shops):
                result_info = f"{total_found}件中 {i+1}件目"
                embed = self.create_shop_embed(shop, result_info)
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"グルメ検索でエラー ({keyword}): {e}", exc_info=True)
            await ctx.send("お店の検索中にエラーが起きちゃったみたい… ごめんなさい！")

    @commands.command(name='randomgourmet', aliases=['ランダムグルメ', 'おなかすいた'], help="条件に合うお店をランダムで1件提案します (例: !aidog randomgourmet 居酒屋)")
    async def random_gourmet(self, ctx: commands.Context, *, keyword: str = "居酒屋 札幌駅"):
        if not self.bot.config.hotpepper_api_key:
            return await ctx.send("ごめんなさいワン… グルメAPIキーがないから、お店を探せないんだワン…。")
            
        await ctx.send(f"`{keyword}` の条件で、素敵なお店をランダムで選んでくるワン！運命の出会いがあるかも…✨")
        try:
            # 1. まずは件数を取得するためのAPIリクエスト
            count_params = {"key": self.bot.config.hotpepper_api_key, "keyword": keyword, "count": 1, "format": "json"}
            async with self.bot.http_session.get(API_BASE_URL, params=count_params) as response:
                response.raise_for_status()
                # ★★★ 修正点2 ★★★
                data = await response.json(content_type='text/javascript;charset=utf-8')

            total_results = int(data.get('results', {}).get('results_available', 0))
            if total_results == 0:
                return await ctx.send(f"`{keyword}` に合うお店は見つからなかったワン… ごめんね！")
            
            max_index = min(total_results, 100)
            random_start_index = random.randint(1, max_index)

            # 2. ランダムな1件を取得するためのAPIリクエスト
            fetch_params = {"key": self.bot.config.hotpepper_api_key, "keyword": keyword, "start": random_start_index, "count": 1, "format": "json"}
            async with self.bot.http_session.get(API_BASE_URL, params=fetch_params) as response:
                response.raise_for_status()
                # ★★★ 修正点3 ★★★
                data = await response.json(content_type='text/javascript;charset=utf-8')

            shop = data.get('results', {}).get('shop', [None])[0]
            if not shop:
                return await ctx.send("ランダムでお店を選ぼうとしたけど、失敗しちゃったワン…")
            
            result_info = f"{total_results}件の中からの一軒"
            embed = self.create_shop_embed(shop, result_info)
            await ctx.send(content=f"ピンときたワン！ **{shop.get('name')}** なんてどうかな？", embed=embed)
        except Exception as e:
            logger.error(f"ランダムグルメ検索でエラー ({keyword}): {e}", exc_info=True)
            await ctx.send("お店の検索中にエラーが起きちゃったみたい… ごめんなさい！")

def setup(bot):
    bot.add_cog(GourmetCog(bot))