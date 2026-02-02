"""
Основний файл бота для моніторингу транзакцій BSC
Простий і надійний підхід
"""
import time
import json
from typing import Set, Optional
from bscscan_client import BSCscanClient
from telegram_bot import TelegramBot
from config import WALLET_ADDRESS, CHECK_INTERVAL, MIN_AMOUNT_USDT, TOKEN_SYMBOL


class PaymentMonitorBot:
    """Бот для моніторингу платежів на BSC"""
    
    def __init__(self):
        self.bscscan = BSCscanClient()
        self.telegram = TelegramBot()
        self.processed_txs: Set[str] = set()
        self.start_block: Optional[int] = None
        self.load_processed_txs()
        self.init_start_block()
        
    def load_processed_txs(self):
        """Завантаження оброблених транзакцій з файлу"""
        try:
            with open('processed_txs.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.processed_txs = set(data.get('txs', []))
                print(f"✅ Завантажено {len(self.processed_txs)} оброблених транзакцій")
        except FileNotFoundError:
            self.processed_txs = set()
            print("📝 Файл processed_txs.json не знайдено, створю новий")
    
    def init_start_block(self):
        """Ініціалізація стартового блоку"""
        self.start_block = self.bscscan.get_latest_block()
        if self.start_block:
            print(f"✅ Стартовий блок: {self.start_block}")
            print(f"📌 Моніторинг почнеться з наступного блоку")
            print(f"⚠️ Увага: Бот перевіряє тільки останні 50 блоків за раз")
            print(f"   Старі транзакції можуть бути пропущені")
        else:
            print("⚠️ Не вдалося отримати стартовий блок")
    
    def save_processed_txs(self):
        """Збереження оброблених транзакцій у файл"""
        try:
            with open('processed_txs.json', 'w', encoding='utf-8') as f:
                json.dump({'txs': list(self.processed_txs)}, f, indent=2)
        except Exception as e:
            print(f"❌ Помилка збереження: {e}")
    
    def check_new_transactions(self):
        """Перевірка нових транзакцій"""
        print(f"\n{'='*60}")
        print(f"🔍 Перевірка транзакцій для {WALLET_ADDRESS}")
        print(f"{'='*60}")
        
        latest_block = self.bscscan.get_latest_block()
        if not latest_block:
            print("❌ Не вдалося отримати останній блок")
            return
        
        if not self.start_block:
            self.start_block = latest_block
            print(f"✅ Встановлено стартовий блок: {self.start_block}")
            return
        
        if latest_block <= self.start_block:
            print("⏳ Нових блоків немає")
            return
        
        # Перевіряємо останні 50 блоків (або менше, якщо нових блоків менше)
        start_block = max(self.start_block + 1, latest_block - 49)
        end_block = latest_block
        
        print(f"📊 Перевірка блоків {start_block} - {end_block} ({end_block - start_block + 1} блоків)")
        
        transactions = self.bscscan.get_token_transactions(
            address=WALLET_ADDRESS,
            start_block=start_block,
            end_block=end_block
        )
        
        if not transactions:
            print("✅ Транзакції не знайдено")
            self.start_block = latest_block
            return
        
        print(f"🎉 Знайдено {len(transactions)} транзакцій USDT!")
        
        # Фільтруємо та обробляємо транзакції
        new_incoming = []
        for tx in transactions:
            tx_hash = tx.get('hash', '')
            
            # Перевіряємо, чи це вхідна транзакція
            if tx.get('to', '').lower() != WALLET_ADDRESS.lower():
                continue
            
            # Перевіряємо, чи вже обробляли
            if tx_hash and tx_hash in self.processed_txs:
                print(f"⏭️ Транзакція {tx_hash[:16]}... вже оброблена")
                continue
            
            # Форматуємо для перевірки
            formatted_tx = self.bscscan.format_transaction(tx)
            
            # Перевіряємо токен
            if formatted_tx['symbol'].upper() != TOKEN_SYMBOL.upper():
                continue
            
            # Перевіряємо мінімальну суму
            if formatted_tx['amount'] < MIN_AMOUNT_USDT:
                print(f"⏭️ Транзакція {tx_hash[:16]}... сума {formatted_tx['amount']:.2f} < {MIN_AMOUNT_USDT}")
                continue
            
            new_incoming.append(tx)
        
        print(f"💰 Знайдено {len(new_incoming)} нових транзакцій >= {MIN_AMOUNT_USDT} USDT")
        
        # Обробляємо нові транзакції
        for tx in new_incoming:
            tx_hash = tx.get('hash', '')
            if not tx_hash:
                continue
            
            formatted_tx = self.bscscan.format_transaction(tx)
            
            print(f"\n💸 НОВА ОПЛАТА!")
            print(f"   Хеш: {tx_hash}")
            print(f"   Сума: {formatted_tx['amount']:.2f} {formatted_tx['symbol']}")
            print(f"   Від: {formatted_tx['from_address']}")
            print(f"   Час: {formatted_tx['timestamp']}")
            
            # Надсилаємо в Telegram
            if self.telegram.send_payment_notification(formatted_tx):
                print(f"   ✅ Повідомлення надіслано в Telegram!")
                self.processed_txs.add(tx_hash)
            else:
                print(f"   ❌ Помилка надсилання в Telegram")
        
        # Оновлюємо стартовий блок
        self.start_block = latest_block
        
        # Зберігаємо оброблені транзакції
        if new_incoming:
            self.save_processed_txs()
    
    def run(self):
        """Запуск бота"""
        print("=" * 60)
        print("🤖 БОТ ЗАПУЩЕНО!")
        print("=" * 60)
        print(f"📍 Адреса: {WALLET_ADDRESS}")
        print(f"💰 Токен: {TOKEN_SYMBOL}")
        print(f"💵 Мінімум: {MIN_AMOUNT_USDT} {TOKEN_SYMBOL}")
        print(f"⏱️ Інтервал: {CHECK_INTERVAL} секунд")
        print("=" * 60)
        print("Натисніть Ctrl+C для зупинки\n")
        
        try:
            while True:
                self.check_new_transactions()
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n\n🛑 Бот зупинено")
            self.save_processed_txs()


import sys

def check_connectivity():
    """Перевірка підключення"""
    errors = []
    warnings = []
    print("🔍 Перевірка підключення...")
    
    # Перевірка QuickNode
    try:
        from bscscan_client import BSCscanClient
        client = BSCscanClient()
        latest_block = client.get_latest_block()
        if latest_block:
            print(f"✅ QuickNode OK. Блок: {latest_block}")
        else:
            warnings.append("⚠️ QuickNode: Не вдалося отримати блок (може бути тимчасово)")
    except Exception as e:
        error_msg = str(e)
        # Витягуємо основну помилку без повного traceback
        if "ConnectionError" in error_msg or "Не вдалося підключитися" in error_msg:
            warnings.append(f"⚠️ QuickNode: Не вдалося підключитися (спроба буде повторена)")
        else:
            warnings.append(f"⚠️ QuickNode: {error_msg}")
    
    # Перевірка Telegram (окремо, без створення PaymentMonitorBot)
    telegram_ok = False
    test_telegram = None
    try:
        from telegram_bot import TelegramBot
        test_telegram = TelegramBot()
        msg = "🤖 Тест: Бот працює!"
        ok = test_telegram.send_message(msg)
        if ok:
            print("✅ Telegram OK")
            telegram_ok = True
        else:
            warnings.append("⚠️ Telegram: Не вдалося відправити тестове повідомлення")
    except Exception as e:
        error_msg = str(e)
        # Витягуємо основну помилку
        if "ConnectionError" in error_msg and "QuickNode" in error_msg:
            # Це помилка від QuickNode, не від Telegram
            pass  # Вже додано вище
        else:
            warnings.append(f"⚠️ Telegram: {error_msg}")
    
    if warnings:
        print("\n⚠️ Попередження:")
        for warn in warnings:
            print(f"   {warn}")
        print("\nБот продовжить роботу, але деякі функції можуть не працювати.")
        print("Перевірте налаштування в config.py якщо проблеми зберігаються.\n")
    
    # Не зупиняємо контейнер навіть якщо є попередження
    # Контейнер має продовжити роботу і спробувати підключитися пізніше
    if telegram_ok and test_telegram:
        # Відправляємо повідомлення про успішний старт тільки якщо Telegram працює
        try:
            test_telegram.send_message("✅ Бот стартував! Моніторинг активний.")
        except:
            pass  # Не критично, якщо не вдалося відправити

if __name__ == "__main__":
    try:
        check_connectivity()
        bot = PaymentMonitorBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Бот зупинено користувачем")
    except Exception as e:
        print(f"\n\n❌ Критична помилка: {e}")
        import traceback
        traceback.print_exc()
        # Не виходимо з sys.exit, щоб контейнер не падав
        # Просто чекаємо і спробуємо перезапустити
        print("\n⏳ Очікування 60 секунд перед повторною спробою...")
        time.sleep(60)
        # Спробуємо перезапустити
        print("🔄 Перезапуск бота...")
        bot = PaymentMonitorBot()
        bot.run()
