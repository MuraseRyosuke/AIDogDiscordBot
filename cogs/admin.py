# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」の管理者向けコマンドを定義するCog。

設定の動的なリロードなど、Botの運用に必要な機能を提供します。
これらのコマンドは、Botのオーナー、またはconfigで指定された
管理者のみが実行できます。
"""

# --- 標準ライブラリのインポート ---
import logging
from typing import TYPE_CHECKING

# --- サードパーティライブラリのインポート ---
import nextcord
from nextcord.ext import commands

# --- 自作モジュールのインポート ---
# from config import load_and_validate_config
# ↑ reloadcfg内で直接呼び出すため、トップレベルでのインポートは不要

# 型ヒントのために 'AIDogBot' クラスをインポートする（循環参照を避ける）
if TYPE_CHECKING:
    from bot_main import AIDogBot
    from utils.conversation_manager import ConversationManager
    from utils.bot_utils import RateLimiter

# このCog用のロガーを取得
logger = logging.getLogger(__name__)


def is_admin():
    """
    コマンド実行者が管理者であるかを確認するカスタムチェック。

    Botのオーナー、または `config.admin_user_ids` に含まれるユーザーを
    管理者と判定します。
    """
    async def predicate(ctx: commands.Context) -> bool:
        # is_owner()はコルーチンのため await が必要
        if await ctx.bot.is_owner(ctx.author):
            return True
        # botインスタンスに紐付けられたconfigから管理者リストを参照
        return ctx.author.id in ctx.bot.config.admin_user_ids
    return commands.check(predicate)


class AdminCog(commands.Cog, name="管理者コマンド"):
    """管理者専用のコマンドをまとめたCog"""

    def __init__(self, bot: 'AIDogBot'):
        self.bot = bot

    @commands.command(
        name='reloadcfg',
        help="設定を再読み込みします（管理者専用）。",
        brief="設定ファイル(.env)を再読み込みします。"
    )
    @is_admin()
    async def reload_config_command(self, ctx: commands.Context):
        """
        環境変数ファイル(.env)から設定を再読み込みし、ボットに適用する。

        このコマンドはBotを再起動することなく、ほとんどの設定を動的に変更します。
        """
        logger.info(f"管理者 {ctx.author.name} ({ctx.author.id}) による設定再読み込み要求。")
        await ctx.send("AI犬、設定ファイルをもう一度読み込んでみるワン！⚙️")

        try:
            # --- 1. 設定の再読み込み ---
            # configモジュールを直接インポートして関数を呼び出す
            from config import load_and_validate_config
            old_config = self.bot.config
            new_config = load_and_validate_config()
            self.bot.config = new_config

            # --- 2. Botコンポーネントへの設定適用 ---
            # !! 注意: 以下の処理は、関連するオブジェクトの状態をリセットします !!
            # 例えば、レートリミッターは全ユーザーの制限状態を初期化します。
            # 会話マネージャーも履歴を再初期化する可能性があります（実装による）。
            self.bot.command_prefix = new_config.command_prefix

            # ConversationManagerとRateLimiterを新しい設定で再インスタンス化
            if hasattr(self.bot, 'conversation_manager'):
                conv_manager_class: 'ConversationManager' = self.bot.conversation_manager.__class__
                self.bot.conversation_manager = conv_manager_class(
                    new_config.max_conversation_history, db_path=new_config.conversation_db_path
                )
                logger.info("ConversationManagerを新しい設定で再初期化しました。")

            if hasattr(self.bot, 'rate_limiter'):
                rate_limiter_class: 'RateLimiter' = self.bot.rate_limiter.__class__
                self.bot.rate_limiter = rate_limiter_class(
                    new_config.rate_limit_per_user, new_config.rate_limit_window
                )
                logger.info("RateLimiterを新しい設定で再初期化しました。")

            logger.info("設定の再適用完了。変更点を比較します。")

            # --- 3. 変更点の比較と通知 ---
            changes = []
            old_config_dict = old_config.__dict__
            for key in sorted(old_config_dict.keys()):
                old_value = old_config_dict.get(key)
                new_value = getattr(new_config, key, None)
                if str(old_value) != str(new_value):
                    changes.append(f"• `{key}`: `{old_value}` → `{new_value}`")

            if changes:
                # DiscordのEmbed descriptionの文字数制限(4096)を考慮
                change_summary = "\n".join(changes)
                if len(change_summary) > 3500:
                    change_summary = change_summary[:3500] + "\n...(長すぎるため省略)"

                embed = nextcord.Embed(
                    title="⚙️ 設定再読み込み完了ワン！",
                    description=f"AI犬が新しい設定でパワーアップ！🔋\n\n**変更点:**\n{change_summary}",
                    color=nextcord.Color.orange()  # 0xffa500
                )
                await ctx.send(embed=embed)
                logger.info(f"設定更新完了。変更点:\n{change_summary}")
            else:
                await ctx.send("設定ファイルは現在の設定と同じだったワン！変更はなかったよ。")
                logger.info("設定再読み込み、変更なし。")

        except SystemExit as e:
            # load_and_validate_configで必須変数が足りない場合に発生
            error_message = f"設定の読み込みに失敗したワン…。必須の項目が足りないみたい。\n`{e}`"
            await ctx.send(error_message)
            logger.error(f"設定再読み込み失敗: {e}")
        except Exception as e:
            await ctx.send(f"設定の再読み込み中に、予期せぬエラーが発生しちゃった…\nエラー: `{str(e)}`")
            logger.error("設定再読み込み中に予期せぬエラーが発生しました。", exc_info=True)


def setup(bot: 'AIDogBot'):
    """CogをBotに登録するためのセットアップ関数"""
    bot.add_cog(AdminCog(bot))