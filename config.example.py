# Приклад конфігураційного файлу
# Скопіюйте цей файл як config.py та заповніть свої дані

# BSCscan налаштування (Etherscan API V2)
# Варіант 1: Etherscan API V2 (потрібна платна підписка для BSC)
BSCSCAN_API_KEY = "YOUR_BSCSCAN_API_KEY"  # Отримайте на https://etherscan.io/myapikey
WALLET_ADDRESS = "0x11b28a56e407d7b89ee1ecf1d1f9748de3fee57b"
BSCSCAN_API_URL = "https://api.etherscan.io/api"  # Etherscan API V2
CHAIN_ID = "56"  # Chain ID для BSC (Binance Smart Chain)

# Варіант 2: BSCTrace через MegaNode (безкоштовно)
# Розкоментуйте наступні рядки та зареєструйтеся на https://meganode.nodereal.io/
# USE_BSCTRACE = True
# BSCTRACE_API_KEY = "YOUR_BSCTRACE_API_KEY"
# BSCTRACE_API_URL = "https://open-platform.nodereal.io"
USE_BSCTRACE = False
BSCTRACE_API_KEY = ""
BSCTRACE_API_URL = "https://open-platform.nodereal.io"

# Telegram налаштування
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Отримайте від @BotFather
TELEGRAM_CHANNEL_ID = "@YOUR_CHANNEL_USERNAME"  # Або ID каналу (наприклад: -1001234567890)

# Налаштування моніторингу
CHECK_INTERVAL = 30  # Інтервал перевірки нових транзакцій (секунди)
MIN_CONFIRMATIONS = 1  # Мінімальна кількість підтверджень

