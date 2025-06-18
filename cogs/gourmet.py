# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」のグルメ検索機能（Cog）。

リクルート提供のホットペッパー Webサービスを利用して、
飲食店情報の検索機能を提供します。
"""

# --- 標準ライブラリのインポート ---
import logging
import random
from typing import TYPE_CHECKING, Dict, Any, Optional

# --- サードパーティライブラリのインポート ---
import aiohttp
import nextcord
from nextcord.ext import commands

# 型ヒントのために 'AIDogBot' クラスをインポートする（循環参照を避ける）
if TYPE_CHECKING:
    from bot_main import AIDogBot


logger = logging.getLogger(__name__)


class GourmetCog(commands.Cog, name="グルメ検索"):
    """ホットペッパーグルメAPIを使ってお店の情報を検索するCog"""

    # --- クラス定数 ---
    API_BASE_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
    # ホットペッパーAPIが返す特殊なContent-Type
    API_CONTENT_TYPE = 'text/javascript;charset=utf-8'

    def __init__(self, bot: 'AIDogBot'):
        self.bot = bot

    def _create_shop_embed(self, shop_data: Dict[str, Any], result_info: Optional[str] = None) -> nextcord.Embed:
        """お店のデータ辞書からEmbedオブジェクトを作成するヘルパー関数。"""
        embed = nextcord.Embed(
            title=shop_data.get('name', '名称不明'),
            url=shop_data.get('urls', {}).get('pc'),
            description=shop_data.get('catch', ''),
            color=nextcord.Color.from_rgb(240, 75, 0)  # ホットペッパーのオレンジ色
        )
        if logo_image := shop_data.get('logo_image'):
            embed.set_thumbnail(url=logo_image)

        embed.add_field(name="ジャンル", value=shop_data.get('genre', {}).get('name', 'N/A'), inline=True)
        embed.add_field(name="アクセス", value=shop_data.get('mobile_access', 'N/A'), inline=False)
        embed.add_field(name="住所", value=shop_data.get('address', 'N/A'), inline=False)
        embed.add_field(name="営業時間", value=shop_data.get('open', 'N/A'), inline=False)

        if large_photo_url := shop_data.get('photo', {}).get('pc', {}).get('l'):
            embed.set_image(url=large_photo_url)

        footer_text = "Powered by ホットペッパー Webサービス"
        if result_info:
            footer_text = f"{result_info} | {footer_text}"
        embed.set_footer(text=footer_text)
        return embed

    @commands.command(name='gourmet', aliases=['グルメ', 'ごはん'], help="指定キーワードでお店を検索します (例: !aidog gourmet 札幌駅 ラーメン)")
    async def gourmet_search(self, ctx: commands.Context, *, keyword: str):
        """指定されたキーワードで飲食店を検索し、上位3件を表示する。"""
        if not self.bot.config.hotpepper_api_key:
            await ctx.send("ごめんなさいワン… グルメAPIキーがないから、お店を探せないんだワン…。")
            return

        processing_msg = await ctx.send(f"`{keyword}` でお店を探してるワン… ちょっと待っててね！🍜")

        params = {
            "key": self.bot.config.hotpepper_api_key,
            "keyword": keyword,
            "count": 3,
            "format": "json"
        }
        try:
            async with self.bot.http_session.get(self.API_BASE_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json(content_type=self.API_CONTENT_TYPE)

            results = data.get('results', {})
            shops = results.get('shop', [])

            if not shops:
                await processing_msg.edit(content=f"`{keyword}` に合うお店は見つからなかったワン… ごめんね！")
                return

            total_found = int(results.get('results_available', 0))
            await processing_msg.edit(content=f"`{keyword}` に合うお店が **{total_found}** 件見つかったワン！トップ{len(shops)}件を紹介するね！")
            
            for i, shop in enumerate(shops):
                result_info = f"{total_found}件中 {i + 1}件目"
                embed = self._create_shop_embed(shop, result_info)
                await ctx.send(embed=embed)

        except aiohttp.ClientResponseError as e:
            logger.error(f"グルメAPIエラー ({keyword}, Status: {e.status}): {e.message}")
            await processing_msg.edit(content=f"お店の検索中にAPIエラーが起きちゃったみたい… (コード: {e.status})")
        except Exception as e:
            logger.error(f"グルメ検索の予期せぬエラー ({keyword}): {e}", exc_info=True)
            await processing_msg.edit(content="お店の検索中に予期せぬエラーが起きちゃったみたい… ごめんなさい！")

    @commands.command(name='randomgourmet', aliases=['ランダムグルメ', 'おなかすいた'], help="条件に合うお店をランダムで1件提案します (例: !aidog randomgourmet 居酒屋)")
    async def random_gourmet(self, ctx: commands.Context, *, keyword: str = "居酒屋 札幌駅"):
        """指定されたキーワードでヒットしたお店の中からランダムで1件を提案する。"""
        if not self.bot.config.hotpepper_api_key:
            await ctx.send("ごめんなさいワン… グルメAPIキーがないから、お店を探せないんだワン…。")
            return

        processing_msg = await ctx.send(f"`{keyword}` の条件で、素敵なお店をランダムで選んでくるワン！運命の出会いがあるかも…✨")
        try:
            # 1. まずは件数を取得するためのAPIリクエスト
            count_params = {
                "key": self.bot.config.hotpepper_api_key,
                "keyword": keyword, "count": 1, "format": "json"
            }
            async with self.bot.http_session.get(self.API_BASE_URL, params=count_params) as response:
                response.raise_for_status()
                data = await response.json(content_type=self.API_CONTENT_TYPE)

            total_results = int(data.get('results', {}).get('results_available', 0))
            if total_results == 0:
                await processing_msg.edit(content=f"`{keyword}` に合うお店は見つからなかったワン… ごめんね！")
                return

            # 2. 取得するお店のランダムなインデックスを決定
            # APIの仕様上、取得可能な上限は1000件程度。負荷も考慮し最大100件から選ぶ。
            max_searchable_index = min(total_results, 100)
            random_start_index = random.randint(1, max_searchable_index)

            # 3. ランダムな1件を取得するためのAPIリクエスト
            fetch_params = {
                "key": self.bot.config.hotpepper_api_key,
                "keyword": keyword, "start": random_start_index, "count": 1, "format": "json"
            }
            async with self.bot.http_session.get(self.API_BASE_URL, params=fetch_params) as response:
                response.raise_for_status()
                data = await response.json(content_type=self.API_CONTENT_TYPE)

            shop = data.get('results', {}).get('shop', [None])[0]
            if not shop:
                await processing_msg.edit(content="ランダムでお店を選ぼうとしたけど、なぜか失敗しちゃったワン…")
                return
            
            result_info = f"{total_results}件の中からの一軒"
            embed = self._create_shop_embed(shop, result_info)
            await processing_msg.edit(content=f"ピンときたワン！ **{shop.get('name')}** なんてどうかな？", embed=embed)

        except aiohttp.ClientResponseError as e:
            logger.error(f"ランダムグルメAPIエラー ({keyword}, Status: {e.status}): {e.message}")
            await processing_msg.edit(content=f"お店の検索中にAPIエラーが起きちゃったみたい… (コード: {e.status})")
        except Exception as e:
            logger.error(f"ランダムグルメ検索の予期せぬエラー ({keyword}): {e}", exc_info=True)
            await processing_msg.edit(content="お店の検索中に予期せぬエラーが起きちゃったみたい… ごめんなさい！")


def setup(bot: 'AIDogBot'):
    """CogをBotに登録するためのセットアップ関数"""
    bot.add_cog(GourmetCog(bot))