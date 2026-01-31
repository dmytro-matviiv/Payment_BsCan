"""
Основний файл бота для моніторингу транзакцій BSCscan
"""
import time
import json
from typing import Set, Optional
from bscscan_client import BSCscanClient
from telegram_bot import TelegramBot
from config import WALLET_ADDRESS, CHECK_INTERVAL, MIN_AMOUNT_USDT, TOKEN_SYMBOL


class PaymentMonitorBot:
    """Бот для моніторингу платежів на BSCscan"""
    
    def __init__(self):
        self.bscscan = BSCscanClient()
        self.telegram = TelegramBot()
        self.processed_txs: Set[str] = set()
        self.start_block: Optional[int] = None  # Блок на момент запуску бота
        self.load_processed_txs()
        self.init_start_block()
        
    def load_processed_txs(self):
        """Завантаження оброблених транзакцій з файлу"""
        try:
            with open('processed_txs.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.processed_txs = set(data.get('txs', []))
        except FileNotFoundError:
            self.processed_txs = set()
    
    def init_start_block(self):
        """Ініціалізація стартового блоку (блок на момент запуску бота)"""
        self.start_block = self.bscscan.get_latest_block()
        if self.start_block:
            print(f"Бот запущено. Початок моніторингу з блоку: {self.start_block}")
            print(f"Будуть оброблятися тільки нові транзакції після цього блоку")
        else:
            print("Попередження: не вдалося отримати стартовий блок")
    
    def save_processed_txs(self):
        """Збереження оброблених транзакцій у файл"""
        try:
            with open('processed_txs.json', 'w', encoding='utf-8') as f:
                json.dump({'txs': list(self.processed_txs)}, f, indent=2)
        except Exception as e:
            print(f"Помилка збереження: {e}")
    
    def check_new_transactions(self):
        """Перевірка нових транзакцій (тільки після запуску бота)"""
        print(f"Перевірка транзакцій для адреси {WALLET_ADDRESS}...")
        
        # Отримуємо останній блок
        latest_block = self.bscscan.get_latest_block()
        if not latest_block:
            print("Не вдалося отримати останній блок")
            print("Перевірте API ключ та підключення до інтернету")
            return
        
        # Якщо стартовий блок не встановлено, встановлюємо його зараз
        if not self.start_block:
            self.start_block = latest_block
            print(f"Встановлено стартовий блок: {self.start_block}")
        
        print(f"Останній блок: {latest_block}, Стартовий блок: {self.start_block}")
        
        # Перевіряємо тільки блоки після запуску бота
        if latest_block <= self.start_block:
            print("Нових блоків немає")
            return
        
        # Отримуємо транзакції тільки з нових блоків
        start_block = self.start_block + 1
        print(f"Пошук транзакцій від блоку {start_block} до {latest_block}")
        
        transactions = self.bscscan.get_token_transactions(
            address=WALLET_ADDRESS,
            start_block=start_block,
            end_block=latest_block
        )
        
        if not transactions:
            print("Транзакції не знайдено")
            # Оновлюємо стартовий блок на поточний
            self.start_block = latest_block
            return
        
        print(f"Знайдено {len(transactions)} транзакцій")
        
        # Фільтруємо транзакції:
        # 1. Тільки вхідні (надійшли на нашу адресу)
        # 2. Тільки USDT
        # 3. Сума >= 1 USDT
        # 4. Ще не оброблені
        new_incoming = []
        for tx in transactions:
            tx_hash = tx.get('hash', '')
            
            # Перевіряємо, чи це вхідна транзакція
            if tx.get('to', '').lower() != WALLET_ADDRESS.lower():
                continue
            
            # Перевіряємо, чи вже обробляли цю транзакцію
            if tx_hash and tx_hash in self.processed_txs:
                continue
            
            # Форматуємо транзакцію для перевірки
            formatted_tx = self.bscscan.format_transaction(tx)
            
            # Перевіряємо токен (тільки USDT)
            if formatted_tx['symbol'].upper() != TOKEN_SYMBOL.upper():
                print(f"Пропущено транзакцію {tx_hash}: не USDT ({formatted_tx['symbol']})")
                continue
            
            # Перевіряємо мінімальну суму (>= 1 USDT)
            if formatted_tx['amount'] < MIN_AMOUNT_USDT:
                print(f"Пропущено транзакцію {tx_hash}: сума {formatted_tx['amount']:.2f} USDT < {MIN_AMOUNT_USDT} USDT")
                continue
            
            new_incoming.append(tx)
        
        print(f"Знайдено {len(new_incoming)} нових транзакцій USDT >= {MIN_AMOUNT_USDT} USDT")
        
        # Обробляємо нові транзакції
        for tx in new_incoming:
            tx_hash = tx.get('hash', '')
            if not tx_hash:
                continue
                
            print(f"Нова транзакція USDT знайдена: {tx_hash}")
            
            # Форматуємо дані транзакції
            formatted_tx = self.bscscan.format_transaction(tx)
            
            # Надсилаємо повідомлення у Telegram
            if self.telegram.send_payment_notification(formatted_tx):
                print(f"Повідомлення надіслано успішно для транзакції {tx_hash}")
                self.processed_txs.add(tx_hash)
            else:
                print(f"Помилка надсилання повідомлення для транзакції {tx_hash}")
        
        # Оновлюємо стартовий блок на поточний
        self.start_block = latest_block
        
        # Зберігаємо оброблені транзакції
        if new_incoming:
            self.save_processed_txs()
    
    def run(self):
        """Запуск бота"""
        print("=" * 60)
        print("БОТ ЗАПУЩЕНО! Моніторинг транзакцій USDT")
        print("=" * 60)
        print(f"Адреса гаманця: {WALLET_ADDRESS}")
        print(f"Токен: {TOKEN_SYMBOL}")
        print(f"Мінімальна сума: {MIN_AMOUNT_USDT} {TOKEN_SYMBOL}")
        print(f"Інтервал перевірки: {CHECK_INTERVAL} секунд")
        print(f"Будуть оброблятися тільки нові транзакції після запуску")
        print("=" * 60)
        print("Натисніть Ctrl+C для зупинки\n")
        
        try:
            while True:
                self.check_new_transactions()
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\nБот зупинено")
            self.save_processed_txs()


import sys

def check_connectivity():
    errors = []
    print("Перевірка доступу до BSC Node (QuickNode)...")
    try:
        # Створюємо клієнт для перевірки підключення
        from bscscan_client import BSCscanClient
        client = BSCscanClient()
        latest_block = client.get_latest_block()
        if latest_block:
            print(f"✅ QuickNode OK. Номер останнього блоку: {latest_block}")
        else:
            raise Exception("Не вдалося отримати номер блоку")
    except Exception as e:
        errors.append(f"❌ QuickNode RPC не працює: {repr(e)}")
        print("\n💡 Підказка:")
        print("   1. Переконайтеся, що ви створили endpoint на https://dashboard.quicknode.com/endpoints/new/bsc")
        print("   2. Виберіть 'Mainnet' (не Testnet)")
        print("   3. Скопіюйте HTTPS URL та вставте його в config.py як QUICKNODE_BSC_NODE")

    print("Перевірка надсилання повідомлень у Telegram...")
    try:
        test_bot = PaymentMonitorBot().telegram
        msg = "🤖 Тест старту: Бот має доступ до QuickNode та Telegram!"
        ok = test_bot.send_message(msg)
        if ok:
            print("✅ Telegram OK: тестове повідомлення відправлено.")
        else:
            raise Exception("Telegram повернув помилку, повідомлення не відправлено")
    except Exception as e:
        errors.append(f"❌ Telegram API не працює: {repr(e)}")

    if errors:
        print("===" )
        print("❌ Помилки під час старту:")
        for err in errors:
            print(" -", err)
        print("===" )
        print("BOT EXITED")
        sys.exit(1)
    else:
        test_bot.send_message("✅ Бот стартував: доступ до QuickNode та Telegram підтверджено. Починаю моніторинг!")

if __name__ == "__main__":
    check_connectivity()
    bot = PaymentMonitorBot()
    bot.run()

