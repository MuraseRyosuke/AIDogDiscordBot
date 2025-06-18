# -*- coding: utf-8 -*-
"""
Discord Bot「AI犬」の設定管理モジュール。

.envファイルから環境変数を読み込み、BotConfigデータクラスに格納します。
設定の読み込み、型変換、バリデーションを一元管理します。
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

# このモジュール用のロガーを取得
logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """
    Botの設定を保持するデータクラス。
    デフォルト値を持つ項目は、環境変数で上書き可能です。
    """
    # --- 必須設定 (環境変数での設定が必須) ---
    bot_token: str
    ollama_model_name: str
    ollama_api_url: str

    # --- 基本設定 ---
    command_prefix: str = "!aidog "
    admin_user_ids: List[int] = field(default_factory=list)

    # --- 応答・会話設定 ---
    max_response_length: int = 1900
    max_conversation_history: int = 5
    conversation_db_path: str = "ai_dog_conversation_history.sqlite3"

    # --- パフォーマンス・制限設定 ---
    request_timeout: int = 180
    rate_limit_per_user: int = 5
    rate_limit_window: int = 60

    # --- Ollamaモデルパラメータ ---
    ollama_temperature: float = 0.7
    ollama_num_ctx: int = 4096
    ollama_top_p: float = 0.9
    ollama_repeat_penalty: float = 1.1

    # --- 拡張機能 (Cog) 向け設定 ---
    # 天気機能
    openweathermap_api_key: Optional[str] = None
    weather_default_city: str = "東京"
    # グルメ検索機能
    hotpepper_api_key: Optional[str] = None
    # (未使用だが将来のためのプレースホルダー)
    progress_update_interval: int = 7


def load_and_validate_config() -> BotConfig:
    """
    環境変数を読み込み、検証し、BotConfigインスタンスを生成して返す。

    必須の環境変数が設定されていない場合は、プログラムを終了させる。

    Returns:
        BotConfig: 設定が格納されたデータクラスのインスタンス。

    Raises:
        SystemExit: 必須の環境変数が不足している場合。
    """
    # .envファイルから環境変数を読み込む
    load_dotenv()
    logger.info(".envファイルを読み込みました。")

    # 1. 必須の環境変数を取得・検証
    required_vars = {
        "bot_token": os.getenv("BOT_TOKEN"),
        "ollama_model_name": os.getenv("OLLAMA_MODEL_NAME"),
        "ollama_api_url": os.getenv("OLLAMA_API_URL"),
    }

    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        error_message = f"致命的エラー: 必須の環境変数が設定されていません: {', '.join(name.upper() for name in missing_vars)}"
        logger.critical(error_message)
        # テスト容易性を考慮すると raise SystemExit が望ましい
        raise SystemExit(error_message)

    # BotConfigインスタンスを必須項目で初期化
    config_instance = BotConfig(**required_vars)

    # 2. 任意の環境変数を読み込み、デフォルト値を上書き
    # (フィールド名, 型変換関数) のタプル
    optional_fields_to_load = [
        ("command_prefix", str),
        ("max_response_length", int),
        ("max_conversation_history", int),
        ("conversation_db_path", str),
        ("request_timeout", int),
        ("rate_limit_per_user", int),
        ("rate_limit_window", int),
        ("ollama_temperature", float),
        ("ollama_num_ctx", int),
        ("ollama_top_p", float),
        ("ollama_repeat_penalty", float),
        ("openweathermap_api_key", str),
        ("weather_default_city", str),
        ("hotpepper_api_key", str),
        ("progress_update_interval", int),
    ]

    for field_name, type_caster in optional_fields_to_load:
        env_var_name = field_name.upper()
        env_val = os.getenv(env_var_name)
        if env_val is not None:
            try:
                # setattrを使って動的にインスタンスの属性を設定
                setattr(config_instance, field_name, type_caster(env_val))
            except (ValueError, TypeError):
                logger.warning(
                    f"環境変数 {env_var_name} の値「{env_val}」を型 '{type_caster.__name__}' に変換できませんでした。デフォルト値を使用します。"
                )

    # 3. 特殊な形式の環境変数をパース (管理者ID)
    admin_user_ids_env = os.getenv("ADMIN_USER_IDS")
    if admin_user_ids_env:
        try:
            # カンマで分割し、空白を除去し、数字のみを抽出してintに変換
            parsed_ids = [int(x.strip()) for x in admin_user_ids_env.split(",") if x.strip().isdigit()]
            if parsed_ids:
                config_instance.admin_user_ids = parsed_ids
            else:
                logger.warning("ADMIN_USER_IDS が設定されていますが、有効な数値のIDが含まれていません。")
        except Exception as e:
            logger.error(f"ADMIN_USER_IDS の解析中にエラーが発生しました: {e}")


    # 4. 最終的な設定値の検証と通知 (APIキーなど)
    if not config_instance.openweathermap_api_key:
        logger.warning("OPENWEATHERMAP_API_KEY が設定されていません。天気機能は利用できません。")
    if not config_instance.hotpepper_api_key:
        logger.warning("HOTPEPPER_API_KEY が設定されていません。グルメ検索機能は利用できません。")

    logger.info("設定の読み込みと検証が完了しました。")
    return config_instance