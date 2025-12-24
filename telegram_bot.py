"""
Модуль для надсилання повідомлень у Telegram
"""
import requests
from typing import Dict, Optional
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID


class TelegramBot:
    """Клас для роботи з Telegram Bot API"""
    
    def __init__(self, bot_token: str = TELEGRAM_BOT_TOKEN):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.channel_id = TELEGRAM_CHANNEL_ID
        
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Надсилання повідомлення у канал"""
        url = f"{self.base_url}/sendMessage"
        params = {
            'chat_id': self.channel_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        try:
            response = requests.post(url, json=params, timeout=10)
            response.raise_for_status()
            return response.json().get('ok', False)
        except requests.exceptions.RequestException as e:
            print(f"Помилка надсилання повідомлення: {e}")
            return False
    
    def format_payment_message(self, tx_data: Dict) -> str:
        """Форматування повідомлення про оплату у форматі як на фото"""
        # Форматуємо суму
        amount_str = f"{tx_data['amount']:.2f} {tx_data['symbol']}"
        
        # Посилання на транзакцію
        tx_hash = tx_data['hash']
        tx_link = f"https://bscscan.com/tx/{tx_hash}"
        
        # Формуємо повідомлення
        message = f"""💰 <b>Нова оплата отримана!</b>

📊 <b>Сума:</b> {amount_str}
📥 <b>Отримано на:</b> <code>{tx_data['to_address']}</code>
🔗 <b>Хеш транзакції:</b> <code>{tx_hash}</code>
🕐 <b>Час:</b> {tx_data['timestamp']}

🔗 <a href="{tx_link}">Переглянути транзакцію</a>"""
        
        return message
    
    def send_payment_notification(self, tx_data: Dict) -> bool:
        """Надсилання сповіщення про оплату"""
        message = self.format_payment_message(tx_data)
        return self.send_message(message)

