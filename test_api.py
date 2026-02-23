"""
Тестовий скрипт для перевірки BSCScan API
"""
from bscscan_client import BSCscanClient
from config import WALLET_ADDRESS


def test_api():
    print("=" * 50)
    print("ТЕСТ BScan API")
    print("=" * 50)
    print(f"📍 Адреса: {WALLET_ADDRESS}")
    print()

    client = BSCscanClient()

    latest_block = client.get_latest_block()
    if not latest_block:
        print("❌ Не вдалося отримати останній блок")
        return
    print(f"✅ Останній блок: {latest_block}")
    print()

    print("🧪 Запуск діагностики...")
    client.run_diagnostic()
    print()

    print("🔍 Пошук USDT за останні 100 блоків...")
    transactions = client.get_token_transactions(
        start_block=latest_block - 99,
        end_block=latest_block
    )

    if transactions:
        print(f"\n✅ Знайдено {len(transactions)} транзакцій")
        tx = transactions[-1]
        formatted = client.format_transaction(tx)
        print(f"📄 Остання:")
        print(f"   Hash: {formatted['hash']}")
        print(f"   Сума: {formatted['amount']:.2f} {formatted['symbol']}")
        print(f"   Від: {formatted['from_address']}")
        print(f"   Час: {formatted['timestamp']}")
    else:
        print("ℹ️ Транзакцій не знайдено за останні 100 блоків")

    print("=" * 50)


if __name__ == "__main__":
    test_api()
