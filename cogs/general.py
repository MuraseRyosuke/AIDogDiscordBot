# cogs/general.py - 本番用
import nextcord
from nextcord.ext import commands
from datetime import datetime

class GeneralCog(commands.Cog, name="一般コマンド"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help', help="AI犬ボットの使い方がわかるワン！") 
    async def custom_help_command(self, ctx: commands.Context):
        embed = nextcord.Embed(
            title="🐾 AI犬ボット ヘルプだワン！ 🐾",
            description=f"ご主人様！AI犬の使い方はこんな感じだワン！\nボクのコマンドプレフィックスは「`{self.bot.config.command_prefix}`」だよ！",
            color=0x3498db, timestamp=datetime.now()
        )
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="💬 AI犬とお話しする方法", value=f"• AI犬にメンション (`@{self.bot.user.name}`) + 聞きたいこと\n• AI犬にDMで聞きたいこと", inline=False)
        command_list = (
            f"• `{self.bot.config.command_prefix}help` - このヘルプを表示\n"
            f"• `{self.bot.config.command_prefix}stats` - ボットの統計情報\n"
            f"• `{self.bot.config.command_prefix}clear` - 会話履歴をリセット\n"
            f"• `{self.bot.config.command_prefix}weather <都市名>` - 天気予報\n"
            f"• `{self.bot.config.command_prefix}bone` - ホネの画像\n"
            f"• `{self.bot.config.command_prefix}reloadcfg` - (管理者のみ) 設定再読み込み"
        )
        embed.add_field(name="🛠️ コマンド一覧", value=command_list, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='stats', help="AI犬ボットの統計情報を表示しますだワン！")
    async def show_stats_command(self, ctx: commands.Context):
        stats_data = self.bot.stats.get_stats()
        embed = nextcord.Embed(title="📊 AI犬ボット統計情報 📊", color=0x2ecc71, timestamp=datetime.now())
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        fields = [
            ("🐕 ボット名", self.bot.user.name, True), ("🧠 モデル", self.bot.config.ollama_model_name, True),
            ("🔌 Ollama", self.bot.ollama_status, True), ("⏱️ 稼働時間", stats_data['uptime'], True),
            ("🗣️ 総リクエスト", stats_data['total_requests'], True), ("📈 成功率", stats_data['success_rate'], True)
        ]
        for name, value, inline in fields: embed.add_field(name=name, value=value, inline=inline)
        await ctx.send(embed=embed)

    @commands.command(name='clear', help="AI犬との会話履歴をリセットするワン！")
    async def clear_history_command(self, ctx: commands.Context):
        deleted_count = self.bot.conversation_manager.clear_user_history(ctx.author.id)
        await ctx.send(f"{ctx.author.mention} ご主人様との思い出（会話ログを{deleted_count}件）、リセットしたワン！")

def setup(bot):
    bot.add_cog(GeneralCog(bot))