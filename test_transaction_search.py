"""
Тестовий скрипт для перевірки пошуку транзакцій з CSV файлу
"""
import csv
from bscscan_client import BSCscanClient
from config import WALLET_ADDRESS

def test_transaction_search():
    """Тестування пошуку транзакцій"""
    print("=" * 60)
    print("ТЕСТ ПОШУКУ ТРАНЗАКЦІЙ")
    print("=" * 60)
    
    # Читаємо CSV файл
    csv_file = r"d:\export-token-transfer-0x11B28A56E407d7b89eE1ECF1d1F9748de3Fee57B.csv"
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            transactions = list(reader)
        
        print(f"✅ Завантажено {len(transactions)} транзакцій з CSV")
        print()
        
        # Аналізуємо транзакції
        print("📊 Аналіз транзакцій:")
        tokens = {}
        for tx in transactions:
            token = tx.get('Token', '').strip()
            if token:
                tokens[token] = tokens.get(token, 0) + 1
        
        for token, count in tokens.items():
            print(f"   {token}: {count} транзакцій")
        
        print()
        print(f"⚠️ Увага: В CSV немає транзакцій USDT!")
        print(f"   Бот шукає тільки USDT (контракт: 0x55d398326f99059fF775485246999027B3197955)")
        print()
        
        # Знаходимо найновішу та найстарішу транзакцію
        if transactions:
            blocks = [int(tx.get('BlockNo', 0)) for tx in transactions if tx.get('BlockNo', '').isdigit()]
            if blocks:
                min_block = min(blocks)
                max_block = max(blocks)
                print(f"📦 Діапазон блоків у CSV: {min_block} - {max_block}")
                print(f"   Різниця: {max_block - min_block} блоків")
                print()
        
        # Тестуємо пошук транзакцій через API
        print("🔍 Тестування пошуку через API...")
        client = BSCscanClient()
        
        # Отримуємо поточний блок
        latest_block = client.get_latest_block()
        if latest_block:
            print(f"✅ Поточний блок: {latest_block}")
            
            if blocks:
                # Перевіряємо, чи блоки з CSV ще доступні
                if max_block < latest_block:
                    blocks_behind = latest_block - max_block
                    print(f"⚠️ Найновіша транзакція в CSV на {blocks_behind} блоків позаду")
                    print(f"   Бот перевіряє тільки останні 50 блоків")
                    print(f"   Транзакції з CSV можуть бути занадто старі")
                else:
                    print(f"✅ Блоки з CSV актуальні")
        else:
            print("❌ Не вдалося отримати поточний блок")
        
        print()
        
        # Спробуємо знайти транзакцію з CSV
        if transactions:
            test_tx = transactions[1]  # Друга транзакція (перша - заголовок)
            tx_hash = test_tx.get('Transaction Hash', '').strip('"')
            block_no = test_tx.get('BlockNo', '').strip()
            token = test_tx.get('Token', '').strip()
            
            print(f"🧪 Тестування пошуку транзакції:")
            print(f"   Hash: {tx_hash}")
            print(f"   Block: {block_no}")
            print(f"   Token: {token}")
            print()
            
            if tx_hash:
                print("Спроба знайти транзакцію через API...")
                found_tx = client.check_transaction_by_hash(tx_hash)
                if found_tx:
                    print(f"✅ Транзакцію знайдено через API!")
                    print(f"   From: {found_tx.get('from', '')}")
                    print(f"   To: {found_tx.get('to', '')}")
                    print(f"   Value: {found_tx.get('value', '')}")
                else:
                    print(f"❌ Транзакцію не знайдено через API")
                    print(f"   Можливі причини:")
                    print(f"   - Це не USDT транзакція (бот шукає тільки USDT)")
                    print(f"   - Помилка API через rate limiting")
                    print(f"   - Неправильний hash транзакції")
        
    except FileNotFoundError:
        print(f"❌ Файл не знайдено: {csv_file}")
    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_transaction_search()
