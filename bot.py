"""
Бот для моніторингу USDT платежів на BSC.
Використовує RPC (QuickNode/GetBlock) для пошуку транзакцій.
"""
import time
import json
from typing import Set, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bscscan_client import BSCscanClient
from telegram_bot import TelegramBot
from config import WALLET_ADDRESS, CHECK_INTERVAL, MIN_AMOUNT_USDT, TOKEN_SYMBOL


class PaymentMonitorBot:
    def __init__(self):
        self.bscscan = BSCscanClient()
        self.telegram = TelegramBot()
        self.processed_txs: Set[str] = set()
        self.start_block: Optional[int] = None
        self.kyiv_tz = ZoneInfo("Europe/Kyiv")
        self.quiet_start_hour = 1
        self.quiet_end_hour = 9
        self.is_quiet_mode = False
        self.load_processed_txs()
        self.bscscan.run_diagnostic()
        self.init_start_block()

    def _now_kyiv(self) -> datetime:
        return datetime.now(self.kyiv_tz)

    def _is_quiet_hours(self, now_kyiv: datetime) -> bool:
        return self.quiet_start_hour <= now_kyiv.hour < self.quiet_end_hour

    def _send_status_message(self, text: str):
        try:
            self.telegram.send_message(text)
        except Exception as e:
            print(f"⚠️ Не вдалося надіслати системне повідомлення: {e}")

    def _seconds_to_next_transition(self, now_kyiv: datetime, is_quiet: bool) -> int:
        if is_quiet:
            transition = now_kyiv.replace(
                hour=self.quiet_end_hour, minute=0, second=0, microsecond=0
            )
            if transition <= now_kyiv:
                transition = transition + timedelta(days=1)
        else:
            transition = now_kyiv.replace(
                hour=self.quiet_start_hour, minute=0, second=0, microsecond=0
            )
            if transition <= now_kyiv:
                transition = transition + timedelta(days=1)

        seconds = int((transition - now_kyiv).total_seconds())
        return max(1, seconds)

    def load_processed_txs(self):
        try:
            with open('processed_txs.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.processed_txs = set(data.get('txs', []))
                print(f"✅ Завантажено {len(self.processed_txs)} оброблених транзакцій")
        except FileNotFoundError:
            self.processed_txs = set()
            print("📝 Файл processed_txs.json не знайдено, створю новий")

    def init_start_block(self):
        self.start_block = self.bscscan.get_latest_block()
        if self.start_block:
            print(f"✅ Стартовий блок: {self.start_block}")
            print(f"📌 Моніторинг почнеться з наступного блоку")
        else:
            print("⚠️ Не вдалося отримати стартовий блок")

    def save_processed_txs(self):
        try:
            with open('processed_txs.json', 'w', encoding='utf-8') as f:
                json.dump({'txs': list(self.processed_txs)}, f, indent=2)
        except Exception as e:
            print(f"❌ Помилка збереження: {e}")

    def check_new_transactions(self):
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

        start = self.start_block + 1
        print(f"📊 Перевірка блоків {start} - {latest_block} ({latest_block - start + 1} блоків)")

        transactions = self.bscscan.get_token_transactions(
            start_block=start,
            end_block=latest_block
        )

        self.start_block = latest_block

        new_incoming = []
        for tx in transactions:
            tx_hash = tx.get('hash', '')
            if not tx_hash:
                continue
            if tx.get('to', '').lower() != WALLET_ADDRESS.lower():
                continue
            if tx_hash in self.processed_txs:
                continue

            formatted = self.bscscan.format_transaction(tx)
            if formatted['symbol'].upper() != TOKEN_SYMBOL.upper():
                continue
            if formatted['amount'] < MIN_AMOUNT_USDT:
                continue

            new_incoming.append(tx)

        if not new_incoming:
            print("✅ Нових платежів не знайдено")
            return

        print(f"💰 Знайдено {len(new_incoming)} нових транзакцій >= {MIN_AMOUNT_USDT} USDT!")

        for tx in new_incoming:
            tx_hash = tx.get('hash', '')
            formatted = self.bscscan.format_transaction(tx)
            print(f"\n💸 НОВА ОПЛАТА!")
            print(f"   Хеш: {tx_hash}")
            print(f"   Сума: {formatted['amount']:.2f} {formatted['symbol']}")
            print(f"   Від: {formatted['from_address']}")
            print(f"   Час: {formatted['timestamp']}")

            if self.telegram.send_payment_notification(formatted):
                print(f"   ✅ Повідомлення надіслано в Telegram!")
                self.processed_txs.add(tx_hash)
            else:
                print(f"   ❌ Помилка надсилання в Telegram")

        self.save_processed_txs()

    def run(self):
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
        print("🌐 Метод: RPC (QuickNode/GetBlock)")
        print("🕐 Тихий період (Київ): 01:00-09:00")
        print("=" * 60)
        print("Натисніть Ctrl+C для зупинки\n")

        try:
            while True:
                now_kyiv = self._now_kyiv()
                in_quiet = self._is_quiet_hours(now_kyiv)

                if in_quiet:
                    if not self.is_quiet_mode:
                        self.is_quiet_mode = True
                        self._send_status_message(
                            "🌙 01:00 (Київ): моніторинг призупинено до 09:00."
                        )
                        print("🌙 Тихий період: моніторинг призупинено до 09:00 (Київ)")

                    sleep_seconds = self._seconds_to_next_transition(now_kyiv, is_quiet=True)
                    time.sleep(sleep_seconds)
                    continue

                if self.is_quiet_mode:
                    self.is_quiet_mode = False
                    self._send_status_message(
                        "🌅 09:00 (Київ): моніторинг відновлено, продовжую роботу."
                    )
                    print("🌅 Моніторинг відновлено о 09:00 (Київ)")

                self.check_new_transactions()
                now_after_check = self._now_kyiv()
                sleep_seconds = min(
                    CHECK_INTERVAL, self._seconds_to_next_transition(now_after_check, is_quiet=False)
                )
                time.sleep(sleep_seconds)
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
