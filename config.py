# Конфігураційний файл для бота моніторингу USDT платежів (BSC)
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# === RPC endpoints ===
# Моніторинг працює тільки через RPC, без BSCScan/Etherscan API.
QUICKNODE_BSC_NODE = os.getenv(
    "QUICKNODE_BSC_NODE",
    "https://still-orbital-snow.bsc.quiknode.pro/e60ffc8002adabba4d011e493be35d07d4f9ca26/",
)
GETBLOCK_BSC_NODE = os.getenv(
    "GETBLOCK_BSC_NODE",
    "https://go.getblock.us/6331e58511e54706be53c9b4d8ce9ad2",
)

# Адреса гаманця для моніторингу
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x11b28a56e407d7b89ee1ecf1d1f9748de3fee57b")

# Telegram налаштування
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8456055614:AAFeuIrPgQKDdfl_e9ULHi1oAJimxkaeLWM")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@payment_trc20_001")

# Налаштування моніторингу
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))  # Інтервал перевірки (секунди) — 3 хвилини
MIN_AMOUNT_USDT = float(os.getenv("MIN_AMOUNT_USDT", "1.0"))  # Мінімальна сума транзакції в USDT
TOKEN_SYMBOL = os.getenv("TOKEN_SYMBOL", "USDT")  # Токен для моніторингу

# Налаштування підключення
INITIAL_CONNECTION_DELAY = float(
    os.getenv("INITIAL_CONNECTION_DELAY", "5.0")
)  # Затримка перед першим підключенням (секунди)
USE_FALLBACK_ENDPOINT = _env_bool("USE_FALLBACK_ENDPOINT", True)  # Використовувати GetBlock якщо QuickNode недоступний
