# Конфігураційний файл для бота

# TokenView API налаштування
# Використовує API: https://services.tokenview.io/
# Документація: https://services.tokenview.io/docs/api/blockchain/overview.html
WALLET_ADDRESS = "0x11b28a56e407d7b89ee1ecf1d1f9748de3fee57b"

# TokenView API ключ (обов'язково)
# Отримайте безкоштовний ключ на https://services.tokenview.io/en/dashboard
# Безкоштовний план: до 300 запитів на хвилину
USE_NODEREAL = True
NODEREAL_API_KEY = "bnzIpAa6vSopsMfnuKQ4"  # TokenView Address Tracking API ключ

# Telegram налаштування
TELEGRAM_BOT_TOKEN = "8456055614:AAFeuIrPgQKDdfl_e9ULHi1oAJimxkaeLWM"  # Отримайте від @BotFather
TELEGRAM_CHANNEL_ID = "@payment_trc20_001"  # Або ID каналу (наприклад: -1001234567890)

# Налаштування моніторингу
CHECK_INTERVAL = 30  # Інтервал перевірки нових транзакцій (секунди)
MIN_CONFIRMATIONS = 1  # Мінімальна кількість підтверджень
MIN_AMOUNT_USDT = 1.0  # Мінімальна сума транзакції в USDT
TOKEN_SYMBOL = "USDT"  # Токен для моніторингу (тільки USDT)

