"""
Основний файл бота для моніторингу транзакцій BSC
На основі Repush7 з економними налаштуваннями
"""
import time
import json
from typing import Set, Optional
from bscscan_client import BSCscanClient
from telegram_bot import TelegramBot
from config import WALLET_ADDRESS, CHECK_INTERVAL, MIN_AMOUNT_USDT, TOKEN_SYMBOL, MAX_BLOCKS_PER_CHECK, REQUEST_DELAY


class PaymentMonitorBot:
    """Бот для моніторингу платежів на BSC"""
    
    def __init__(self):
        self.bscscan = BSCscanClient()
        self.telegram = TelegramBot()
        self.processed_txs: Set[str] = set()
        self.start_block: Optional[int] = None
        self.load_processed_txs()
        self.bscscan.run_diagnostic()
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
        
        # Перевіряємо ВСІ неперевірені блоки по черзі (чанками по MAX_BLOCKS_PER_CHECK).
        # Раніше: start_block = max(..., latest-9) — це ПРОПУСКАЛО блоки! Платіж у 82686936 був пропущений.
        start_block = self.start_block + 1
        new_incoming = []
        
        while start_block <= latest_block:
            end_block = min(start_block + (MAX_BLOCKS_PER_CHECK - 1), latest_block)
            print(f"📊 Перевірка блоків {start_block} - {end_block} ({end_block - start_block + 1} блоків)")
            
            transactions = self.bscscan.get_token_transactions(
                start_block=start_block,
                end_block=end_block
            )
            
            for tx in transactions:
                tx_hash = tx.get('hash', '')
                if tx.get('to', '').lower() != WALLET_ADDRESS.lower():
                    continue
                if tx_hash and tx_hash in self.processed_txs:
                    continue
                formatted_tx = self.bscscan.format_transaction(tx)
                if formatted_tx['symbol'].upper() != TOKEN_SYMBOL.upper():
                    continue
                if formatted_tx['amount'] < MIN_AMOUNT_USDT:
                    continue
                new_incoming.append(tx)
            
            self.start_block = end_block
            start_block = end_block + 1
            
            if start_block <= latest_block:
                time.sleep(REQUEST_DELAY)  # пауза між чанками
        
        if not new_incoming:
            print("✅ Транзакції не знайдено")
            return
        
        print(f"💰 Знайдено {len(new_incoming)} нових транзакцій >= {MIN_AMOUNT_USDT} USDT")
        
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
            if self.telegram.send_payment_notification(formatted_tx):
                print(f"   ✅ Повідомлення надіслано в Telegram!")
                self.processed_txs.add(tx_hash)
            else:
                print(f"   ❌ Помилка надсилання в Telegram")
        
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
        if CHECK_INTERVAL >= 60:
            print(f"⏱️ Інтервал: {CHECK_INTERVAL // 60} хв ({CHECK_INTERVAL} сек)")
        else:
            print(f"⏱️ Інтервал: {CHECK_INTERVAL} сек")
        print(f"📦 Блоків за перевірку: {MAX_BLOCKS_PER_CHECK}")
        print("=" * 60)
        print("Натисніть Ctrl+C для зупинки\n")
        
        try:
            while True:
                self.check_new_transactions()
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n\n🛑 Бот зупинено")
            self.save_processed_txs()


if __name__ == "__main__":
    bot = PaymentMonitorBot()
    try:
        tg = TelegramBot()
        tg.send_message("✅ Бот стартував! Моніторинг активний.")
        print("✅ Telegram OK")
    except Exception as e:
        print(f"⚠️ Telegram: {e}")
    bot.run()
