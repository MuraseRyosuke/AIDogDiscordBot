import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, Tuple

class RateLimiter:
    """ユーザーごとのリクエストレートを制限するクラス"""
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[int, deque] = defaultdict(deque)

    def is_rate_limited(self, user_id: int) -> Tuple[bool, int]:
        """レート制限に達しているかチェックし、達していなければリクエストを記録する"""
        now = time.time()
        user_reqs = self.requests[user_id]
        
        # ウィンドウ外の古いタイムスタンプを削除
        while user_reqs and now - user_reqs[0] > self.window_seconds:
            user_reqs.popleft()
            
        if len(user_reqs) >= self.max_requests:
            wait_time = int(self.window_seconds - (now - user_reqs[0]) + 1)
            return True, wait_time
            
        user_reqs.append(now)
        return False, 0

class BotStats:
    """ボットの統計情報を記録・管理するクラス"""
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_response_time = 0.0
        self.start_time = datetime.now()

    def record_request(self, success: bool, response_time: float):
        """リクエスト結果を記録する"""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            self.total_response_time += response_time
        else:
            self.failed_requests += 1

    def get_stats(self) -> dict:
        """現在の統計情報を辞書形式で取得する"""
        uptime_delta = datetime.now() - self.start_time
        uptime_str = str(timedelta(seconds=int(uptime_delta.total_seconds())))
        
        avg_response_time = (self.total_response_time / self.successful_requests if self.successful_requests > 0 else 0)
        success_rate = (self.successful_requests / self.total_requests * 100 if self.total_requests > 0 else 0)

        return {
            'uptime': uptime_str,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{success_rate:.1f}%" if self.total_requests > 0 else "N/A",
            'avg_response_time': f"{avg_response_time:.2f}s"
        }