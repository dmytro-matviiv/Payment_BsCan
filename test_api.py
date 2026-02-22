"""
Тестовий скрипт для перевірки роботи QuickNode BSC API
"""
from bscscan_client import BSCscanClient
from config import WALLET_ADDRESS

def test_api():
    """Тестування QuickNode BSC API"""
    print("=" * 50)
    print("ТЕСТ ПІДКЛЮЧЕННЯ ДО QUICKNODE BSC")
    print("=" * 50)
    print(f"📍 Адреса гаманця: {WALLET_ADDRESS}")
    print()
    
    client = BSCscanClient()
    latest_block = client.get_latest_block()
    if not latest_block:
        print("❌ Не вдалося отримати останній блок")
        return
    print(f"✅ Останній блок: {latest_block}")
    print()
    
    print("Тест пошуку USDT транзакцій (останні 50 блоків)...")
    transactions = client.get_token_transactions(
        start_block=latest_block - 49,
        end_block=latest_block
    )
    
    if transactions:
        print(f"✅ Знайдено {len(transactions)} транзакцій USDT")
        last_tx = transactions[0]
        formatted = client.format_transaction(last_tx)
        print(f"📄 Hash: {last_tx.get('hash', '')}")
        print(f"💰 Сума: {formatted['amount']:.2f} {formatted['symbol']}")
        print(f"📤 Від: {formatted['from_address']}")
        print(f"📥 До: {formatted['to_address']}")
    else:
        print("Транзакції не знайдено (можливо немає в останніх 50 блоках)")
    print("=" * 50)

if __name__ == "__main__":
    test_api()
