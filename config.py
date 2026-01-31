# Конфігураційний файл для бота через QuickNode (BSC)

# QuickNode RPC Endpoint URL (отримайте на https://dashboard.quicknode.com/endpoints/new/bsc)
# Після створення endpoint на QuickNode, скопіюйте HTTPS URL сюди
QUICKNODE_BSC_NODE = "https://clean-magical-season.bsc.quiknode.pro/df5393b39afc0e2be5e6bd805bb6f86eba2a8514/"  # QuickNode endpoint URL
# Приклад: "https://your-endpoint-name.bsc.quiknode.pro/your-api-key/"

# Старий GetBlock NODE URL (залишено для резерву)
GETBLOCK_BSC_NODE = "https://go.getblock.us/6331e58511e54706be53c9b4d8ce9ad2"

# Адреса гаманця для моніторингу
WALLET_ADDRESS = "0x11b28a56e407d7b89ee1ecf1d1f9748de3fee57b"

# Telegram налаштування
TELEGRAM_BOT_TOKEN = "8456055614:AAFeuIrPgQKDdfl_e9ULHi1oAJimxkaeLWM"  # Отримайте від @BotFather
TELEGRAM_CHANNEL_ID = "@payment_trc20_001"  # Або ID каналу (наприклад: -1001234567890)

# Налаштування моніторингу
CHECK_INTERVAL = 30  # Інтервал перевірки нових транзакцій (секунди)
MIN_CONFIRMATIONS = 1  # Мінімальна кількість підтверджень
MIN_AMOUNT_USDT = 1.0  # Мінімальна сума транзакції в USDT
TOKEN_SYMBOL = "USDT"  # Токен для моніторингу (тільки USDT)

# Налаштування rate limiting (для уникнення 429 помилок)
REQUEST_DELAY = 1.0  # Затримка між запитами до блоків (секунди)
MAX_RETRIES = 8  # Максимальна кількість спроб при 429 помилці
RETRY_BASE_DELAY = 5.0  # Базова затримка для retry (секунди, буде збільшуватися експоненційно)
MAX_RETRY_DELAY = 120.0  # Максимальна затримка для retry (секунди)
INITIAL_CONNECTION_DELAY = 10.0  # Затримка перед першою спробою підключення (секунди)
USE_FALLBACK_ENDPOINT = True  # Використовувати резервний endpoint (GETBLOCK) якщо QuickNode не працює