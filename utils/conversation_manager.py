import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ConversationManager:
    """会話履歴をSQLiteデータベースで管理するクラス"""
    def __init__(self, max_history_for_context: int = 5, db_path: str = 'ai_dog_conversation_history.sqlite3'):
        self.max_history_for_context = max_history_for_context
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """データベースとテーブルを初期化する"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL
                    )''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_timestamp ON conversation_log (user_id, timestamp)')
                conn.commit()
            logger.info(f"SQLite DB '{self.db_path}' 準備完了だワン。")
        except sqlite3.Error as e:
            logger.error(f"SQLite DB初期化エラー: {e}")

    def add_message(self, user_id: int, user_msg: str, bot_response: str):
        """ユーザーとボットのメッセージをDBに追加する"""
        now_iso = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # ユーザーの発言を記録
                cursor.execute("INSERT INTO conversation_log (user_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                               (str(user_id), now_iso, 'user', user_msg))
                # ボットの応答を記録
                cursor.execute("INSERT INTO conversation_log (user_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                               (str(user_id), datetime.now().isoformat(), 'assistant', bot_response))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"会話ログDB保存エラー (User: {user_id}): {e}")

    def get_context(self, user_id: int) -> str:
        """指定されたユーザーの直近の会話履歴をコンテキストとして取得する"""
        context_parts = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 履歴の新しいものから指定件数*2(往復分)を取得
                cursor.execute("SELECT role, content FROM conversation_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                               (str(user_id), self.max_history_for_context * 2))
                rows = cursor.fetchall()
                if rows:
                    # 時系列が正しくなるように逆順にしてから処理
                    for role, content in reversed(rows):
                        # コンテキストが長くなりすぎないように200文字に制限
                        context_parts.append(f"以前の{'ご主人様' if role == 'user' else 'AI犬'}の言葉: {content[:200]}")
                    logger.info(f"User: {user_id} のコンテキストをDBから {len(rows)//2} 往復分生成。")
        except sqlite3.Error as e:
            logger.error(f"コンテキスト取得SQLiteエラー (User: {user_id}): {e}")
            return "以前の会話を読み込めなかったワン..."
            
        return "\n".join(context_parts) if context_parts else "これが最初の会話だワン！"

    def clear_user_history(self, user_id: int) -> int:
        """指定されたユーザーの会話履歴をすべて削除する"""
        deleted_count = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM conversation_log WHERE user_id = ?", (str(user_id),))
                deleted_count = cursor.rowcount
                conn.commit()
            logger.info(f"User: {user_id} の会話履歴をDBから {deleted_count} 件削除。")
        except sqlite3.Error as e:
            logger.error(f"会話ログDB削除エラー (User: {user_id}): {e}")
        return deleted_count