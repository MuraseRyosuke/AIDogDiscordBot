import nextcord
from nextcord.ext import commands
import io
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class FunCog(commands.Cog, name="お楽しみコマンド"):
    """天気予報やファイル送信など、楽しむための機能を集めたCog"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='weather', aliases=['天気', 'てんき'], help="指定都市の天気をお知らせ！ (例: !aidog weather 東京)")
    async def weather_command(self, ctx: commands.Context, *, city: Optional[str] = None):
        if not self.bot.config.openweathermap_api_key:
            await ctx.send("ごめんなさいワン…お天気APIキーがないから、お天気をお知らせできないんだワン…。"); return

        target_city = city or self.bot.config.weather_default_city
        if not target_city:
            await ctx.send(f"どこのお天気が知りたいワン？ `{self.bot.config.command_prefix}weather 都市名` で教えて！"); return

        # --- ★★★ ここが修正点です ★★★ ---
        # URLはベース部分のみを記述
        url = "http://api.openweathermap.org/data/2.5/weather"
        # 都市名やAPIキーなどのパラメータは、安全な辞書形式で渡す
        params = {
            'q': target_city,
            'appid': self.bot.config.openweathermap_api_key,
            'lang': 'ja',
            'units': 'metric'
        }
        
        processing_msg = await ctx.send(f"`{target_city}`のお天気を調べてるワン…🌦️")

        try:
            # http_session.get に url と params を渡してリクエスト
            async with self.bot.http_session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            city_name = data.get("name", target_city)
            desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            t_min = data["main"]["temp_min"]
            t_max = data["main"]["temp_max"]
            humidity = data["main"]["humidity"]
            wind = data["wind"]["speed"]
            
            weather_text_for_llm = (f"今日の{city_name}の天気は「{desc}」、気温{temp}°C（最高{t_max}°C、最低{t_min}°C）、湿度は{humidity}%、風速{wind}mです。"
                                    f"この天気について、AI犬として何か一言コメントしてください。例えば「お散歩に最高だワン！」とか「今日は傘がいるかも？」のように、天気に合わせた楽しくて役立つ短いコメントをお願いします。")
            
            # ask_ai_inuはbotインスタンスに紐づいていないので、直接は呼べません。
            # bot_main.pyで定義したヘルパー関数を呼び出すように修正が必要です。
            # ただし、現在の構造では直接呼べないので、一時的にコメント生成をスキップします。
            # (もし ask_ai_inu を使いたい場合は、bot_main.pyからこの関数に bot インスタンスを渡す必要があります)
            # weather_comment, success, _ = await self.bot.ask_ai_inu(weather_text_for_llm, ctx.author.id)
            weather_comment = "お出かけの参考にしてほしいワン！🐾" # 一時的なコメント
            success = True

            embed = nextcord.Embed(title=f"🐕 {city_name}のお天気情報だワン！", color=0x7289da, timestamp=datetime.now())
            embed.add_field(name="天気", value=desc.capitalize(), inline=True)
            embed.add_field(name="気温", value=f"{temp:.1f}°C", inline=True)
            embed.add_field(name="最高/最低", value=f"{t_max:.1f}°C / {t_min:.1f}°C", inline=True)
            embed.add_field(name="湿度", value=f"{humidity}%", inline=True)
            embed.add_field(name="風速", value=f"{wind:.1f} m/s", inline=True)
            if success and weather_comment:
                embed.add_field(name="AI犬からの一言", value=weather_comment, inline=False)
            
            icon_id = data["weather"][0]["icon"]
            embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{icon_id}@2x.png")
            embed.set_footer(text=f"情報取得元: OpenWeatherMap")
            await processing_msg.edit(content=None, embed=embed)

        except aiohttp.ClientResponseError as e:
            logger.error(f"天気APIエラー ({target_city}, Status: {e.status}): {e.message}")
            if e.status == 401:
                await processing_msg.edit(content="お天気情報の取得に失敗… APIキーが無効みたいだワン。")
            elif e.status == 404:
                await processing_msg.edit(content=f"`{target_city}`が見つからなかったワン… 都市名を確認してみてね。")
            else:
                await processing_msg.edit(content="お天気情報の取得中にエラーが発生しちゃった…")
        except Exception as e:
            logger.error(f"天気処理エラー({target_city}): {e}", exc_info=True)
            await processing_msg.edit(content="お天気処理で予期せぬエラーが発生しちゃったワン！")

    @commands.command(name='bone', help="AI犬からホネの画像をもらうワン！🦴")
    async def send_bone_picture(self, ctx: commands.Context):
        image_path = Path("bot_images/bone.png")
        if image_path.exists():
            try:
                await ctx.send(f"{ctx.author.mention} ご主人様、ホネをどうぞだワン！🦴", file=nextcord.File(image_path))
            except Exception as e:
                logger.error(f"画像送信エラー ({image_path}): {e}")
                await ctx.send("くぅーん、ホネを渡そうとしたけど失敗しちゃったワン…")
        else:
            logger.warning(f"画像ファイルが見つかりません: {image_path}")
            await ctx.send("わん！ホネの画像が見つからないワン…お腹すいちゃったのかな？")

    @commands.command(name='textfile', help="AI犬からサンプルテキストファイルをもらうワン！")
    async def send_text_file(self, ctx: commands.Context):
        file_content = "これはAI犬からご主人様への秘密のメッセージだワン！\nいつもありがとうだワン！大好きだワン！🐾"
        buffer = io.BytesIO(file_content.encode('utf-8'))
        await ctx.send(f"{ctx.author.mention} サンプルテキストファイルをどうぞだワン！📄", file=nextcord.File(buffer, filename="ai_inu_secret_message.txt"))

def setup(bot):
    bot.add_cog(FunCog(bot))