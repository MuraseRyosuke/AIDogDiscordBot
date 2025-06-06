import nextcord
from nextcord.ext import commands
from config import load_and_validate_config
import logging

logger = logging.getLogger(__name__)

# --- 管理者チェック用のカスタムデコレータ ---
def is_admin():
    """コマンド実行者がconfigのADMIN_USER_IDSに含まれているかチェックする"""
    async def predicate(ctx: commands.Context) -> bool:
        # ボットのオーナーも暗黙的に管理者とみなす
        if await ctx.bot.is_owner(ctx.author):
            return True
        return ctx.author.id in ctx.bot.config.admin_user_ids
    return commands.check(predicate)

class AdminCog(commands.Cog, name="管理者コマンド"):
    """管理者専用のコマンドをまとめたCog"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='reloadcfg', help="設定を再読み込みします（管理者専用）。")
    @is_admin() # is_owner()の代わりにカスタムチェックを使用
    async def reload_config_command(self, ctx: commands.Context):
        """環境変数ファイル(.env)から設定を再読み込みし、ボットに適用する"""
        logger.info(f"管理者 {ctx.author.name} ({ctx.author.id}) による設定再読み込み要求。")
        
        try:
            old_config_dict = self.bot.config.__dict__.copy()
            
            # 新しい設定を読み込む
            new_config = load_and_validate_config()
            self.bot.config = new_config
            
            # ボットの各コンポーネントに新しい設定を適用
            self.bot.command_prefix = new_config.command_prefix
            self.bot.conversation_manager = self.bot.conversation_manager.__class__(new_config.max_conversation_history, db_path=new_config.conversation_db_path)
            self.bot.rate_limiter = self.bot.rate_limiter.__class__(new_config.rate_limit_per_user, new_config.rate_limit_window)
            
            logger.info("設定の再適用完了。変更点を比較します。")

            # 変更点を比較して表示
            changes = [
                f"• `{key}`: `{old_config_dict.get(key)}` → `{getattr(new_config, key, 'N/A')}`"
                for key in sorted(old_config_dict.keys())
                if str(old_config_dict.get(key)) != str(getattr(new_config, key, None))
            ]

            if changes:
                change_summary = "\n".join(changes)
                if len(change_summary) > 3000: # Discordの埋め込みフィールドの制限を考慮
                    change_summary = change_summary[:3000] + "\n...(長すぎるため省略)"

                embed = nextcord.Embed(title="⚙️ 設定再読み込み完了ワン！", description=f"AI犬が新しい設定でパワーアップ！🔋\n**変更点:**\n{change_summary}", color=0xffa500)
                await ctx.send(embed=embed)
                logger.info(f"設定更新完了。変更点:\n{change_summary}")
            else:
                await ctx.send("設定ファイルは現在の設定と同じだったワン！")
                logger.info("設定再読み込み、変更なし。")

        except Exception as e:
            await ctx.send(f"設定再読み込み失敗…エラー: {str(e)}")
            logger.error("設定再読み込みエラー", exc_info=True)

def setup(bot):
    bot.add_cog(AdminCog(bot))