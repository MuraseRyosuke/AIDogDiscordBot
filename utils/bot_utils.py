# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」で利用するユーティリティクラス群。

- RateLimiter: ユーザーごとのコマンド実行頻度を制限する。
- BotStats: Botの稼働状況やリクエストに関する統計情報を管理する。
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Tuple, Any


class RateLimiter:
    """
    ユーザーごとのリクエストレートを制限するクラス。
    スライディングウィンドウアルゴリズムを使用します。
    """

    def __init__(self, max_requests: int, window_seconds: int):
        """
        RateLimiterを初期化します。

        Args:
            max_requests (int): 制限時間内に許容されるリクエストの最大数。
            window_seconds (int): 制限時間を秒単位で指定。
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # {user_id: deque([timestamp1, timestamp2, ...])}
        self.requests: Dict[int, Deque[float]] = defaultdict(deque)

    def is_rate_limited(self, user_id: int) -> Tuple[bool, int]:
        """
        指定されたユーザーがレート制限に達しているかを確認します。

        制限に達していない場合は、今回のリクエストを記録します。
        制限に達している場合は、次のリクエストが可能になるまでの待機時間を返します。

        Args:
            user_id (int): DiscordユーザーのID。

        Returns:
            Tuple[bool, int]: (レート制限に達しているか, 待機時間(秒))
        """
        now = time.time()
        user_reqs = self.requests[user_id]

        # 制限時間外の古いタイムスタンプをdequeの左側から削除
        while user_reqs and now - user_reqs[0] > self.window_seconds:
            user_reqs.popleft()

        if len(user_reqs) >= self.max_requests:
            # 制限に達している場合、待機時間を計算
            # 最初のタイムスタンプからの経過時間をウィンドウ秒数から引き、
            # 少数点以下を切り上げて1秒足すことで、確実な待機時間を確保する
            wait_time = int(self.window_seconds - (now - user_reqs[0])) + 1
            return True, wait_time

        # 制限に達していない場合、現在のタイムスタンプを記録
        user_reqs.append(now)
        return False, 0


class BotStats:
    """ボットの統計情報を記録・管理するクラス"""

    def __init__(self):
        """BotStatsを初期化し、統計の記録を開始します。"""
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.total_response_time: float = 0.0
        self.start_time: datetime = datetime.now()

    def record_request(self, success: bool, response_time: float) -> None:
        """
        AIへのリクエスト結果を記録します。

        Args:
            success (bool): リクエストが成功したかどうか。
            response_time (float): 応答にかかった時間（秒）。
        """
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            self.total_response_time += response_time
        else:
            self.failed_requests += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        現在の統計情報を辞書形式で取得します。

        このメソッドは、呼び出し側がそのまま表示に使えるよう、
        稼働時間や成功率などを整形済みの文字列として返します。

        Returns:
            Dict[str, Any]: 統計情報を含む辞書。
        """
        uptime_delta = datetime.now() - self.start_time
        # 秒未満を切り捨てて、"days, H:M:S" 形式の文字列に変換
        uptime_str = str(timedelta(seconds=int(uptime_delta.total_seconds())))

        # ゼロ除算を回避
        avg_response_time = (
            self.total_response_time / self.successful_requests
            if self.successful_requests > 0 else 0.0
        )
        success_rate = (
            (self.successful_requests / self.total_requests) * 100
            if self.total_requests > 0 else 0.0
        )

        return {
            'uptime': uptime_str,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{success_rate:.1f}%" if self.total_requests > 0 else "N/A",
            'avg_response_time': f"{avg_response_time:.2f}s"
        }