# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」のお楽しみ機能（Cog）。

天気予報や画像送信など、インタラクティブなコマンドを提供します。
"""

# --- 標準ライブラリのインポート ---
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Dict, Any

# --- サードパーティライブラリのインポート ---
import aiohttp
import nextcord
from nextcord.ext import commands

# 型ヒントのために 'AIDogBot' クラスをインポートする（循環参照を避ける）
if TYPE_CHECKING:
    from bot_main import AIDogBot


logger = logging.getLogger(__name__)


class FunCog(commands.Cog, name="お楽しみコマンド"):
    """天気予報やファイル送信など、楽しむための機能を集めたCog"""

    # --- 定数定義 ---
    WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
    WEATHER_ICON_URL_TEMPLATE = "https://openweathermap.org/img/wn/{icon_id}@2x.png"
    BONE_IMAGE_PATH = Path("bot_images/bone.png")

    def __init__(self, bot: 'AIDogBot'):
        self.bot = bot

    async def _fetch_weather_data(self, city: str) -> Dict[str, Any]:
        """OpenWeatherMap APIから天気データを取得する。"""
        params = {
            'q': city,
            'appid': self.bot.config.openweathermap_api_key,
            'lang': 'ja',
            'units': 'metric'
        }
        async with self.bot.http_session.get(self.WEATHER_API_URL, params=params) as response:
            # ステータスコードが200番台でない場合は例外を発生させる
            response.raise_for_status()
            return await response.json()

    def _create_weather_embed(self, data: Dict[str, Any], city_name: str) -> nextcord.Embed:
        """APIデータから天気情報のEmbedオブジェクトを作成する。"""
        # .get()を使い、APIレスポンスの構造が一部欠けていてもエラーにならないようにする
        weather_info = data.get('weather', [{}])[0]
        main_info = data.get('main', {})
        wind_info = data.get('wind', {})

        desc = weather_info.get('description', '情報なし')
        icon_id = weather_info.get('icon')
        temp = main_info.get('temp')
        temp_min = main_info.get('temp_min')
        temp_max = main_info.get('temp_max')
        humidity = main_info.get('humidity')
        wind_speed = wind_info.get('speed')

        embed = nextcord.Embed(
            title=f"🐕 {data.get('name', city_name)}のお天気情報だワン！",
            color=nextcord.Color.blue(),  # 0x7289da
            timestamp=datetime.now()
        )
        embed.add_field(name="天気", value=desc.capitalize(), inline=True)
        embed.add_field(name="気温", value=f"{temp:.1f}°C" if temp is not None else "N/A", inline=True)
        embed.add_field(name="最高/最低", value=f"{temp_max:.1f}°C / {temp_min:.1f}°C" if temp_max and temp_min else "N/A", inline=True)
        embed.add_field(name="湿度", value=f"{humidity}%" if humidity is not None else "N/A", inline=True)
        embed.add_field(name="風速", value=f"{wind_speed:.1f} m/s" if wind_speed is not None else "N/A", inline=True)
        embed.add_field(name="AI犬からの一言", value="お出かけの参考にしてほしいワン！🐾", inline=False)

        if icon_id:
            embed.set_thumbnail(url=self.WEATHER_ICON_URL_TEMPLATE.format(icon_id=icon_id))
        embed.set_footer(text="情報取得元: OpenWeatherMap")

        return embed

    @commands.command(name='weather', aliases=['天気', 'てんき'], help="指定都市の天気をお知らせ！ (例: !aidog weather 東京)")
    async def weather_command(self, ctx: commands.Context, *, city: Optional[str] = None):
        """
        指定された都市の現在の天気をOpenWeatherMapから取得して表示する。
        都市が指定されない場合は、設定されたデフォルトの都市が使用される。
        """
        # 1. APIキーの存在チェック (ガード節)
        if not self.bot.config.openweathermap_api_key:
            await ctx.send("ごめんなさいワン…お天気APIキーがないから、お天気をお知らせできないんだワン…。")
            return

        # 2. 対象都市の決定
        target_city = city or self.bot.config.weather_default_city
        if not target_city:
            await ctx.send(f"どこのお天気が知りたいワン？ `{self.bot.config.command_prefix}weather 都市名` で教えて！")
            return

        processing_msg = await ctx.send(f"`{target_city}`のお天気を調べてるワン…🌦️")

        # 3. データ取得とEmbed作成
        try:
            weather_data = await self._fetch_weather_data(target_city)
            weather_embed = self._create_weather_embed(weather_data, target_city)
            await processing_msg.edit(content=None, embed=weather_embed)

        # 4. エラーハンドリング
        except aiohttp.ClientResponseError as e:
            logger.error(f"天気APIエラー ({target_city}, Status: {e.status}): {e.message}")
            if e.status == 401:
                await processing_msg.edit(content="お天気情報の取得に失敗… APIキーが無効みたいだワン。")
            elif e.status == 404:
                await processing_msg.edit(content=f"`{target_city}`が見つからなかったワン… ローマ字で試してみてね。")
            else:
                await processing_msg.edit(content=f"お天気情報の取得中にエラーが発生しちゃった… (コード: {e.status})")
        except Exception as e:
            logger.error(f"天気コマンドの予期せぬエラー({target_city}): {e}", exc_info=True)
            await processing_msg.edit(content="お天気処理で予期せぬエラーが発生しちゃったワン！")

    @commands.command(name='bone', help="AI犬からホネの画像をもらうワン！🦴")
    async def send_bone_picture(self, ctx: commands.Context):
        """ローカルに保存された骨の画像を送信する。"""
        if self.BONE_IMAGE_PATH.exists():
            try:
                await ctx.send(
                    f"{ctx.author.mention} ご主人様、ホネをどうぞだワン！🦴",
                    file=nextcord.File(self.BONE_IMAGE_PATH)
                )
            except Exception as e:
                logger.error(f"画像送信エラー ({self.BONE_IMAGE_PATH}): {e}", exc_info=True)
                await ctx.send("くぅーん、ホネを渡そうとしたけど失敗しちゃったワン…")
        else:
            logger.warning(f"画像ファイルが見つかりません: {self.BONE_IMAGE_PATH}")
            await ctx.send("わん！ホネの画像が見つからないワン…お腹すいちゃったのかな？")

    @commands.command(name='textfile', help="AI犬からサンプルテキストファイルをもらうワン！")
    async def send_text_file(self, ctx: commands.Context):
        """動的に生成したテキストメッセージをファイルとして送信する。"""
        file_content = "これはAI犬からご主人様への秘密のメッセージだワン！\nいつもありがとうだワン！大好きだワン！🐾"
        # 文字列をUTF-8でエンコードし、インメモリのバイナリストリームに変換
        buffer = io.BytesIO(file_content.encode('utf-8'))
        await ctx.send(
            f"{ctx.author.mention} サンプルテキストファイルをどうぞだワン！📄",
            file=nextcord.File(buffer, filename="ai_inu_secret_message.txt")
        )


def setup(bot: 'AIDogBot'):
    """CogをBotに登録するためのセットアップ関数"""
    bot.add_cog(FunCog(bot))