import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class BotConfig:
    bot_token: str
    ollama_model_name: str
    ollama_api_url: str
    command_prefix: str = "!aidog "
    max_conversation_history: int = 5
    request_timeout: int = 180
    rate_limit_per_user: int = 5
    rate_limit_window: int = 60
    max_response_length: int = 1900
    admin_user_ids: List[int] = field(default_factory=list)
    conversation_db_path: str = "ai_dog_conversation_history.sqlite3"
    
    ollama_temperature: float = 0.7
    ollama_num_ctx: int = 4096
    ollama_top_p: float = 0.9
    ollama_repeat_penalty: float = 1.1
    progress_update_interval: int = 7

    openweathermap_api_key: Optional[str] = None
    weather_default_city: str = "東京"
    
    hotpepper_api_key: Optional[str] = None

def load_and_validate_config() -> BotConfig:
    load_dotenv()

    bot_token_env = os.getenv("BOT_TOKEN")
    ollama_model_name_env = os.getenv("OLLAMA_MODEL_NAME")
    ollama_api_url_env = os.getenv("OLLAMA_API_URL")

    if not all([bot_token_env, ollama_model_name_env, ollama_api_url_env]):
        missing = [var for var, val in [("BOT_TOKEN", bot_token_env), ("OLLAMA_MODEL_NAME", ollama_model_name_env), ("OLLAMA_API_URL", ollama_api_url_env)] if not val]
        logger.critical(f"致命的エラー: 必須の環境変数が設定されていません: {', '.join(missing)}")
        exit(1)

    admin_ids = []
    admin_user_ids_env = os.getenv("ADMIN_USER_IDS")
    if admin_user_ids_env:
        try:
            admin_ids = [int(x.strip()) for x in admin_user_ids_env.split(",") if x.strip().isdigit()]
            if not admin_ids and admin_user_ids_env: 
                logger.warning("ADMIN_USER_IDS が設定されていますが、有効な数値のIDが含まれていません。")
        except ValueError:
            logger.warning("ADMIN_USER_IDS の形式が不正です。")
    
    config_instance = BotConfig(
        bot_token=bot_token_env, 
        ollama_model_name=ollama_model_name_env, 
        ollama_api_url=ollama_api_url_env, 
        admin_user_ids=admin_ids
    )
    
    # .envから読み込む設定項目
    fields_to_load = {
        "max_conversation_history": int, "request_timeout": int,
        "rate_limit_per_user": int, "rate_limit_window": int, "max_response_length": int,
        "conversation_db_path": str, "ollama_temperature": float, "ollama_num_ctx": int,
        "ollama_top_p": float, "ollama_repeat_penalty": float, "progress_update_interval": int,
        "weather_default_city": str
    }

    # コマンドプレフィックスを BOT_COMMAND_PREFIX から読み込む
    prefix_env = os.getenv("BOT_COMMAND_PREFIX")
    if prefix_env is not None:
        config_instance.command_prefix = str(prefix_env)

    # ループで読み込み
    for field_name, type_caster in fields_to_load.items():
        env_var_name = field_name.upper()
        env_val = os.getenv(env_var_name)
        if env_val is not None:
            try: setattr(config_instance, field_name, type_caster(env_val))
            except (ValueError, TypeError): logger.warning(f"環境変数 {env_var_name} の値「{env_val}」を型変換できませんでした。")

    # APIキーの読み込み
    config_instance.openweathermap_api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not config_instance.openweathermap_api_key:
        logger.warning("OPENWEATHERMAP_API_KEY が設定されていません。天気機能は利用できません。")
        
    config_instance.hotpepper_api_key = os.getenv("HOTPEPPER_API_KEY")
    if not config_instance.hotpepper_api_key:
        logger.warning("HOTPEPPER_API_KEYが設定されていません。グルメ機能は利用できません。")

    return config_instance