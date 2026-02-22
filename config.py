# Конфігураційний файл для бота через QuickNode (BSC)

# QuickNode RPC Endpoint URL (отримайте на https://dashboard.quicknode.com/endpoints/new/bsc)
# Після створення endpoint на QuickNode, скопіюйте HTTPS URL сюди
QUICKNODE_BSC_NODE = "https://clean-magical-season.bsc.quiknode.pro/df5393b39afc0e2be5e6bd805bb6f86eba2a8514"  # QuickNode endpoint URL (без слешу в кінці)
# Приклад: "https://your-endpoint-name.bsc.quiknode.pro/your-api-key/"

# Старий GetBlock NODE URL (залишено для резерву)
GETBLOCK_BSC_NODE = "https://go.getblock.us/6331e58511e54706be53c9b4d8ce9ad2"

# Адреса гаманця для моніторингу
WALLET_ADDRESS = "0x11b28a56e407d7b89ee1ecf1d1f9748de3fee57b"

# Telegram налаштування
TELEGRAM_BOT_TOKEN = "8456055614:AAFeuIrPgQKDdfl_e9ULHi1oAJimxkaeLWM"  # Отримайте від @BotFather
TELEGRAM_CHANNEL_ID = "@payment_trc20_001"  # Або ID каналу (наприклад: -1001234567890)

# Налаштування моніторингу
# Чим більший інтервал, тим менше витрата API credits (але більша затримка виявлення платежу)
CHECK_INTERVAL = 180  # Інтервал перевірки нових транзакцій (секунди) - 3 хвилини
MIN_CONFIRMATIONS = 1  # Мінімальна кількість підтверджень
MIN_AMOUNT_USDT = 1.0  # Мінімальна сума транзакції в USDT
TOKEN_SYMBOL = "USDT"  # Токен для моніторингу (тільки USDT)
MAX_BLOCKS_PER_CHECK = 20  # Максимальна кількість блоків для перевірки за раз

# Чи запитувати timestamp кожного блоку.
# Якщо False, час транзакції буде "N/A", але це суттєво економить API credits (мінус 1 запит на блок).
USE_BLOCK_TIMESTAMP = False

# Налаштування rate limiting
REQUEST_DELAY = 2.0  # Затримка між запитами до блоків (секунди)
INITIAL_CONNECTION_DELAY = 10.0  # Затримка перед першим підключенням (скорочено для Railway)
USE_FALLBACK_ENDPOINT = True  # Використовувати GetBlock якщо QuickNode недоступний