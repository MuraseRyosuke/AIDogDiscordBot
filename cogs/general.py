# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」の一般向けコマンドを定義するCog。

ヘルプ、統計情報、会話履歴のクリアなど、基本的な機能を提供します。
"""

# --- 標準ライブラリのインポート ---
from datetime import datetime
from typing import TYPE_CHECKING

# --- サードパーティライブラリのインポート ---
import nextcord
from nextcord.ext import commands

# 型ヒントのために 'AIDogBot' クラスをインポートする（循環参照を避ける）
if TYPE_CHECKING:
    from bot_main import AIDogBot


class GeneralCog(commands.Cog, name="一般コマンド"):
    """Botの基本的なコマンドをまとめたCog"""

    def __init__(self, bot: 'AIDogBot'):
        self.bot = bot

    @commands.command(name='help', help="AI犬ボットの使い方がわかるワン！")
    async def custom_help_command(self, ctx: commands.Context):
        """
        Botに登録されているコマンドを動的に取得し、
        カテゴリ（Cog）ごとに整理して表示するカスタムヘルプコマンド。
        """
        embed = nextcord.Embed(
            title="🐾 AI犬ボット ヘルプだワン！ 🐾",
            description=f"ご主人様！AI犬の使い方はこんな感じだワン！\n"
                        f"ボクのコマンドプレフィックスは「`{self.bot.config.command_prefix}`」だよ！",
            color=nextcord.Color.blue(),  # 0x3498db
            timestamp=datetime.now()
        )
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(
            name="💬 AI犬とお話しする方法",
            value=f"• AI犬にメンション (`@{self.bot.user.name}`) + 聞きたいこと\n"
                  f"• AI犬とのDMで聞きたいこと",
            inline=False
        )

        # Cogごと（カテゴリごと）にコマンドを動的にリストアップ
        for cog_name, cog in self.bot.cogs.items():
            # コマンドリストを格納するリスト
            command_list = []
            # Cog内のコマンドをループ
            for command in cog.get_commands():
                # hidden=Trueのコマンドは表示しない
                if command.hidden:
                    continue
                
                # ヘルプテキストを取得（なければデフォルトメッセージ）
                help_text = command.help or "説明がないワン…"
                # 管理者コマンドには注釈を付ける
                admin_note = " (管理者のみ)" if cog_name == "管理者コマンド" else ""
                
                command_list.append(f"• `{self.bot.config.command_prefix}{command.name}` - {help_text}{admin_note}")

            if command_list:
                embed.add_field(
                    name=f"🛠️ {cog_name}",
                    value="\n".join(command_list),
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command(name='stats', help="AI犬ボットの統計情報を表示しますだワン！")
    async def show_stats_command(self, ctx: commands.Context):
        """Botの稼働状況やモデル情報などの統計データを表示する。"""
        stats_data = self.bot.stats.get_stats()
        embed = nextcord.Embed(
            title="📊 AI犬ボト統計情報 📊",
            color=nextcord.Color.green(),  # 0x2ecc71
            timestamp=datetime.now()
        )
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # 表示するフィールドをリストで定義
        fields_to_display = [
            ("🐕 ボット名", self.bot.user.name, True),
            ("🧠 モデル", self.bot.config.ollama_model_name, True),
            ("🔌 Ollama状態", self.bot.ollama_status, True),
            ("⏱️ 稼働時間", stats_data.get('uptime', 'N/A'), True),
            ("🗣️ 総リクエスト数", stats_data.get('total_requests', 'N/A'), True),
            ("📈 成功率", stats_data.get('success_rate', 'N/A'), True),
        ]

        for name, value, inline in fields_to_display:
            embed.add_field(name=name, value=value, inline=inline)

        await ctx.send(embed=embed)

    @commands.command(name='clear', help="AI犬との会話履歴をリセットするワン！")
    async def clear_history_command(self, ctx: commands.Context):
        """コマンド実行者の会話履歴をデータベースから削除する。"""
        try:
            deleted_count = self.bot.conversation_manager.clear_user_history(ctx.author.id)
            await ctx.send(
                f"{ctx.author.mention} ご主人様との思い出（会話ログを`{deleted_count}`件）、リセットしたワン！"
            )
            logger.info(f"ユーザー {ctx.author.name} ({ctx.author.id}) が会話履歴をリセットしました。")
        except Exception as e:
            logger.error(f"会話履歴のクリア中にエラーが発生しました (User: {ctx.author.id}): {e}", exc_info=True)
            await ctx.send("ごめんワン…会話履歴のリセット中にエラーが発生しちゃった…。")


def setup(bot: 'AIDogBot'):
    """CogをBotに登録するためのセットアップ関数"""
    bot.add_cog(GeneralCog(bot))