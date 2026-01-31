"""
Швидка перевірка конкретної транзакції та надсилання в Telegram
"""
from bscscan_client import BSCscanClient
from telegram_bot import TelegramBot
from config import WALLET_ADDRESS, MIN_AMOUNT_USDT

# Хеш транзакції для перевірки
TX_HASH = "0xc76a2b45c012aadc0fb56bb4f64621e9818598296548b5a9a1b0034e14133eae"

def check_and_send():
    """Перевірка транзакції та надсилання в Telegram"""
    print("=" * 60)
    print("ПЕРЕВІРКА ТРАНЗАКЦІЇ ТА НАДСИЛАННЯ В TELEGRAM")
    print("=" * 60)
    print(f"Хеш: {TX_HASH}")
    print(f"Адреса: {WALLET_ADDRESS}")
    print("=" * 60)
    
    # Створюємо клієнт
    client = BSCscanClient()
    telegram = TelegramBot()
    
    # Перевіряємо транзакцію
    print("\n🔍 Перевірка транзакції...")
    tx = client.check_transaction_by_hash(TX_HASH)
    
    if not tx:
        print("❌ Транзакція не знайдена або не містить USDT Transfer на вашу адресу")
        return
    
    print(f"✅ Транзакція знайдена!")
    print(f"   Блок: {tx['blockNumber']}")
    print(f"   Від: {tx['from']}")
    print(f"   До: {tx['to']}")
    
    # Форматуємо транзакцію
    formatted_tx = client.format_transaction(tx)
    
    print(f"\n💰 Деталі:")
    print(f"   Сума: {formatted_tx['amount']:.2f} {formatted_tx['symbol']}")
    print(f"   Час: {formatted_tx['timestamp']}")
    
    # Перевіряємо мінімальну суму
    if formatted_tx['amount'] < MIN_AMOUNT_USDT:
        print(f"⚠️ Сума {formatted_tx['amount']:.2f} USDT менша за мінімум {MIN_AMOUNT_USDT} USDT")
        return
    
    # Надсилаємо в Telegram
    print(f"\n📱 Надсилання повідомлення в Telegram...")
    if telegram.send_payment_notification(formatted_tx):
        print(f"✅ Повідомлення надіслано успішно!")
    else:
        print(f"❌ Помилка надсилання повідомлення")

if __name__ == "__main__":
    check_and_send()
