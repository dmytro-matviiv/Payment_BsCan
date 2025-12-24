"""
Тестовий скрипт для перевірки роботи NodeReal API
"""
from bscscan_client import BSCscanClient
from config import WALLET_ADDRESS, NODEREAL_API_KEY

def test_api():
    """Тестування TokenView API"""
    print("=" * 50)
    print("ТЕСТ ПІДКЛЮЧЕННЯ ДО TOKENVIEW API")
    print("=" * 50)
    
    print(f"📍 Адреса гаманця: {WALLET_ADDRESS}")
    
    # TokenView Address Tracking API ключ обов'язковий
    if NODEREAL_API_KEY and len(NODEREAL_API_KEY) > 5:
        print(f"✅ TokenView Address Tracking API ключ встановлено: {NODEREAL_API_KEY[:10]}...")
    else:
        print("❌ TokenView API ключ не встановлено!")
        print("   Отримайте безкоштовний ключ на https://services.tokenview.io/en/dashboard")
        print("   Додайте ключ у config.py як NODEREAL_API_KEY")
        return
    
    print()
    
    client = BSCscanClient()
    
    # Тест 1: Отримання останнього блоку
    print("Тест 1: Отримання останнього блоку...")
    latest_block = client.get_latest_block()
    if latest_block:
        print(f"✅ Останній блок: {latest_block}")
    else:
        print("❌ Не вдалося отримати останній блок")
        print("   Пробуємо продовжити з транзакціями...")
        latest_block = 99999999  # Використовуємо велике число для пошуку всіх транзакцій
    print()
    
    # Тест 2: Отримання транзакцій
    print("Тест 2: Отримання транзакцій токенів USDT...")
    # TokenView API не потребує обмеження діапазону блоків, але для тесту використаємо останні 100000 блоків
    search_range = min(100000, latest_block)
    print(f"Пошук транзакцій від блоку {max(0, latest_block - search_range)} до {latest_block}")
    transactions = client.get_token_transactions(
        address=WALLET_ADDRESS,
        start_block=max(0, latest_block - search_range),
        end_block=latest_block
    )
    
    if transactions:
        print(f"✅ Знайдено {len(transactions)} транзакцій USDT")
        print("\n" + "=" * 50)
        print("ОСТАННЯ ТРАНЗАКЦІЯ:")
        print("=" * 50)
        
        # Остання транзакція - перша в списку (бо вони відсортовані від найновіших)
        last_tx = transactions[0]
        formatted = client.format_transaction(last_tx)
        
        print(f"\n📄 Hash транзакції: {last_tx.get('hash', 'N/A')}")
        print(f"🔗 Посилання: https://bsctrace.com/tx/{last_tx.get('hash', '')}")
        print(f"\n📤 Від адреси: {formatted['from_address']}")
        print(f"📥 До адреси: {formatted['to_address']}")
        print(f"\n💰 Токен: {formatted['symbol']}")
        print(f"💵 Сума: {formatted['amount']:.2f} {formatted['symbol']}")
        print(f"\n🕐 Час: {formatted['timestamp']}")
        print(f"📦 Блок: {last_tx.get('blockNumber', 'N/A')}")
        print(f"📋 Контракт: {formatted['contract_address']}")
        print(f"\n{'✅ Вхідна транзакція' if formatted['is_incoming'] else '❌ Вихідна транзакція'}")
        print("=" * 50)
    else:
        print("❌ Транзакції не знайдено")
        print("   Можливі причини:")
        print("   - На цій адресі немає транзакцій USDT")
        print("   - Транзакції занадто старі (поза діапазоном пошуку)")
        print("   - Проблеми з підключенням до RPC")
    
    print()
    print("=" * 50)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 50)

if __name__ == "__main__":
    test_api()

