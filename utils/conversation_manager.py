# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」の会話履歴管理モジュール。

SQLiteデータベースを使用して、ユーザーごとの会話履歴を永続的に保存・管理します。
"""

import logging
import sqlite3
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    会話履歴をSQLiteデータベースで管理するクラス。

    各メソッドは呼び出されるたびにDBに接続・切断するため、
    ステートレスでスレッドセーフな操作を保証します。
    """
    # --- SQLクエリ定義 ---
    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS conversation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL
        )
    """
    _CREATE_INDEX_SQL = """
        CREATE INDEX IF NOT EXISTS idx_user_id_timestamp 
        ON conversation_log (user_id, timestamp)
    """
    _INSERT_LOG_SQL = """
        INSERT INTO conversation_log (user_id, timestamp, role, content) 
        VALUES (?, ?, ?, ?)
    """
    _SELECT_CONTEXT_SQL = """
        SELECT role, content FROM conversation_log 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    """
    _DELETE_USER_HISTORY_SQL = "DELETE FROM conversation_log WHERE user_id = ?"

    def __init__(self, max_history_for_context: int = 5, db_path: str = 'ai_dog_conversation_history.sqlite3'):
        """
        ConversationManagerを初期化します。

        Args:
            max_history_for_context (int): LLMに渡す文脈に含める会話の往復数。
            db_path (str): SQLiteデータベースファイルのパス。
        """
        self.max_history_for_context = max_history_for_context
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """データベースファイルとテーブルが存在しない場合に初期化する。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(self._CREATE_TABLE_SQL)
                cursor.execute(self._CREATE_INDEX_SQL)
                conn.commit()
            logger.info(f"SQLite DB '{self.db_path}' の準備が完了しました。")
        except sqlite3.Error as e:
            logger.critical(f"SQLite DBの初期化に失敗しました: {e}", exc_info=True)
            raise

    def add_message(self, user_id: int, user_msg: str, bot_response: str) -> None:
        """
        ユーザーの発言とそれに対するBotの応答を、単一のトランザクションでDBに追加する。

        Args:
            user_id (int): DiscordユーザーのID。
            user_msg (str): ユーザーの発言内容。
            bot_response (str): Botの応答内容。
        """
        # ユーザーの発言とBotの応答で同じタイムスタンプを使用し、一連のやり取りとする
        timestamp = datetime.now().isoformat()
        messages_to_add = [
            (user_id, timestamp, 'user', user_msg),
            (user_id, timestamp, 'assistant', bot_response),
        ]
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(self._INSERT_LOG_SQL, messages_to_add)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"会話ログのDB保存に失敗しました (User: {user_id}): {e}", exc_info=True)

    def get_context(self, user_id: int) -> str:
        """
        指定されたユーザーの直近の会話履歴を、LLM向けのコンテキスト文字列として取得する。

        Args:
            user_id (int): DiscordユーザーのID。

        Returns:
            str: 整形されたコンテキスト文字列。
        """
        context_parts: List[str] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 1往復 = 2レコード(user, assistant)なので、取得数は*2する
                limit = self.max_history_for_context * 2
                cursor.execute(self._SELECT_CONTEXT_SQL, (user_id, limit))
                rows = cursor.fetchall()

                # DBからは新しい順で取得されるため、逆順にして時系列を正しくする
                for role, content in reversed(rows):
                    speaker = "ご主人様" if role == 'user' else "AI犬"
                    # コンテキストが長くなりすぎないよう、各発言を200文字に制限
                    truncated_content = content[:200] + '…' if len(content) > 200 else content
                    context_parts.append(f"以前の{speaker}の言葉: {truncated_content}")

                if rows:
                    logger.info(f"User: {user_id} のコンテキストをDBから {len(rows)//2} 往復分生成しました。")

        except sqlite3.Error as e:
            logger.error(f"コンテキストの取得中にDBエラーが発生しました (User: {user_id}): {e}", exc_info=True)
            return "以前の会話履歴を読み込めませんでしたワン…"

        return "\n".join(context_parts) if context_parts else "これが最初の会話だワン！"

    def clear_user_history(self, user_id: int) -> int:
        """
        指定されたユーザーの会話履歴をすべて削除する。

        Args:
            user_id (int): DiscordユーザーのID。

        Returns:
            int: 削除されたレコードの件数。
        """
        deleted_count = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(self._DELETE_USER_HISTORY_SQL, (user_id,))
                deleted_count = cursor.rowcount
                conn.commit()
            logger.info(f"User: {user_id} の会話履歴をDBから {deleted_count} 件削除しました。")
        except sqlite3.Error as e:
            logger.error(f"会話ログのDB削除中にエラーが発生しました (User: {user_id}): {e}", exc_info=True)

        return deleted_count