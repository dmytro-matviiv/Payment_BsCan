"""
Модуль для роботи з BSC через TokenView Address Tracking API
Використовує API: https://services.tokenview.io/
Документація: https://services.tokenview.io/docs/track.html
"""
import requests
import time
import json
from typing import List, Dict, Optional
from config import (
    WALLET_ADDRESS,
    USE_NODEREAL, NODEREAL_API_KEY
)

# USDT контракт на BSC
USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"

# TokenView API endpoint
TOKENVIEW_API_BASE = "https://services.tokenview.io/vipapi"


class BSCscanClient:
    """Клієнт для роботи з BSC через TokenView API"""
    
    def __init__(self, api_key: str = None):
        self.use_nodereal = USE_NODEREAL
        if api_key:
            self.api_key = api_key
        else:
            # Використовуємо TokenView API ключ з конфігурації
            self.api_key = NODEREAL_API_KEY if USE_NODEREAL and NODEREAL_API_KEY else ""
        
        self.api_base = TOKENVIEW_API_BASE
        self.last_block = None
        
        print(f"TokenView Address Tracking API: {self.api_base}")
        if self.api_key:
            print(f"✅ TokenView Address Tracking API ключ встановлено: {self.api_key[:10]}...")
        else:
            print("⚠️  TokenView API ключ не встановлено")
            print("   Додайте ключ у config.py як NODEREAL_API_KEY")
    
    def _make_api_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Виконання запиту до TokenView API"""
        if params is None:
            params = {}
        
        # Додаємо API ключ до параметрів
        if self.api_key:
            params['apikey'] = self.api_key
        
        url = f"{self.api_base}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Перевіряємо структуру відповіді TokenView
            if data.get('code') == 1:  # TokenView використовує code=1 для успіху
                data_content = data.get('data', {})
                # Дані можуть бути в data.txs або просто data як список
                if isinstance(data_content, dict):
                    return data_content.get('txs', data_content.get('list', []))
                elif isinstance(data_content, list):
                    return data_content
                else:
                    return []
            elif data.get('code') == 0:
                # Помилка від API
                error_msg = data.get('msg', data.get('message', 'Unknown error'))
                print(f"Помилка TokenView API: {error_msg}")
                return None
            else:
                # Можливо, дані без обгортки або інша структура
                if isinstance(data, dict) and 'data' in data:
                    return data['data'] if isinstance(data['data'], list) else []
                return data if isinstance(data, list) else []
                
        except requests.exceptions.RequestException as e:
            print(f"Помилка запиту до TokenView API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    print(f"Відповідь сервера: {error_data}")
                except:
                    print(f"Відповідь сервера: {e.response.text}")
            return None
    
    def get_token_transactions(self, address: str = WALLET_ADDRESS, start_block: int = 0, 
                               end_block: int = 99999999) -> List[Dict]:
        """Отримання токен транзакцій для адреси через TokenView API"""
        return self._get_token_transactions_via_tokenview(address, start_block, end_block)
    
    def _get_token_transactions_via_tokenview(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Отримання транзакцій токенів через TokenView Address Tracking API"""
        print(f"Пошук USDT транзакцій для адреси {address}")
        print(f"Блоки: {start_block} - {end_block}")
        
        # TokenView Address Tracking API - Webhook History endpoint
        # Документація: https://services.tokenview.io/docs/track.html
        # Endpoint: /vipapi/monitor/webhookhistory/{chain}?page={page}&apikey={apikey}
        # Повертає історичні повідомлення для всіх адрес однієї блокчейн мережі (100 записів на сторінку)
        
        all_transactions = []
        page = 1
        
        while True:
            endpoint = f"monitor/webhookhistory/bsc"  # BSC = bsc (lowercase)
            
            params = {
                'page': page
            }
            
            print(f"Запит сторінки {page} до: {self.api_base}/{endpoint}")
            response_data = self._make_api_request(endpoint, params)
            
            if response_data is None:
                print(f"Не вдалося отримати дані на сторінці {page}")
                break
            
            # Обробляємо відповідь від webhookhistory endpoint
            # Структура відповіді:
            # {
            #   "code": 1,
            #   "msg": "success",
            #   "data": {
            #     "page": 1,
            #     "size": 100,
            #     "total": 200,
            #     "list": [...]
            #   }
            # }
            
            transactions_list = []
            
            if isinstance(response_data, dict):
                if 'list' in response_data:
                    transactions_list = response_data['list']
                elif 'data' in response_data:
                    if isinstance(response_data['data'], dict) and 'list' in response_data['data']:
                        transactions_list = response_data['data']['list']
                    elif isinstance(response_data['data'], list):
                        transactions_list = response_data['data']
            elif isinstance(response_data, list):
                transactions_list = response_data
            
            if not transactions_list:
                print(f"Транзакції не знайдено на сторінці {page}")
                break
            
            print(f"Знайдено {len(transactions_list)} записів на сторінці {page}")
            
            # Фільтруємо транзакції для нашої адреси та USDT
            filtered_txs = []
            for tx in transactions_list:
                try:
                    # У webhook history дані можуть бути в полі 'request' (JSON рядок)
                    request_data = tx.get('request')
                    if request_data and isinstance(request_data, str):
                        try:
                            request_json = json.loads(request_data)
                            # Об'єднуємо дані з request у tx (request має пріоритет)
                            tx = {**tx, **request_json}
                        except Exception as e:
                            # Якщо не вдалося розпарсити, використовуємо tx як є
                            pass
                    
                    # Перевіряємо адресу (тільки для нашої адреси)
                    tx_address = (tx.get('address') or '').lower()
                    if tx_address != address.lower():
                        continue
                    
                    # Перевіряємо блок
                    block_num = tx.get('height') or tx.get('blockHeight') or tx.get('blockNo')
                    if block_num:
                        try:
                            block_num = int(block_num) if isinstance(block_num, (int, str)) else 0
                            if block_num < start_block or block_num > end_block:
                                continue
                        except:
                            pass
                    
                    # Перевіряємо токен (тільки USDT)
                    token_symbol = (tx.get('tokenSymbol') or '').upper()
                    token_address = (tx.get('tokenAddress') or '').lower()
                    
                    is_usdt = (
                        token_symbol == 'USDT' or 
                        token_address == USDT_CONTRACT_BSC.lower()
                    )
                    
                    if not is_usdt:
                        continue
                    
                    # Перевіряємо, чи це вхідна транзакція (tokenValue не має знаку "-")
                    # В webhook history tokenValue може бути рядком, де "-" означає вихідну
                    value_str = str(tx.get('tokenValue') or tx.get('value') or '0')
                    is_incoming = not value_str.startswith('-')
                    
                    if is_incoming:
                        filtered_txs.append(self._format_webhook_transaction(tx))
                except Exception as e:
                    print(f"Помилка обробки транзакції: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            all_transactions.extend(filtered_txs)
            
            # Якщо отримано менше 100 записів, це остання сторінка
            if len(transactions_list) < 100:
                break
            
            page += 1
            
            # Запобігаємо занадто багатьом запитам
            if page > 100:  # Максимум 100 сторінок
                print("Досягнуто максимальну кількість сторінок (100)")
                break
            
            # Затримка між запитами
            time.sleep(0.2)
        
        print(f"Всього знайдено {len(all_transactions)} вхідних транзакцій USDT")
        return all_transactions
    
    def _format_webhook_transaction(self, tx: Dict) -> Dict:
        """Форматування транзакції з TokenView Webhook History у стандартний формат"""
        # Отримуємо значення tokenValue (зміна балансу токену)
        # tokenValue у webhook може бути вже конвертованим значенням (не в wei)
        value_str = str(tx.get('tokenValue') or tx.get('value') or '0')
        
        # Видаляємо знак "-" якщо є (для вхідних транзакцій він не повинен бути)
        is_negative = value_str.startswith('-')
        if is_negative:
            value_str = value_str[1:]
        if value_str.startswith('+'):
            value_str = value_str[1:]
        
        # Конвертуємо значення
        # tokenValue зазвичай вже в десятковому форматі (наприклад "100.5" означає 100.5 USDT)
        try:
            value_decimal = float(value_str)
            # BSC USDT має 18 decimals, але tokenValue може бути вже в правильному форматі
            # Якщо це маленьке число (< 1000000), то це вже конвертоване значення
            if abs(value_decimal) < 1000000:
                # Конвертуємо з USDT в wei (18 decimals)
                value = int(value_decimal * (10 ** 18))
            else:
                # Можливо вже в wei форматі
                value = int(value_decimal)
        except:
            # Якщо не вдалося, спробуємо як ціле число
            try:
                value = int(value_str)
            except:
                value = 0
        
        # Отримуємо timestamp
        timestamp = tx.get('time') or tx.get('timestamp') or 0
        if isinstance(timestamp, str):
            try:
                timestamp = int(timestamp)
            except:
                timestamp = 0
        elif not isinstance(timestamp, int):
            timestamp = 0
        
        # Отримуємо block number
        block_number = tx.get('height') or tx.get('blockHeight') or 0
        if isinstance(block_number, str):
            try:
                block_number = int(block_number)
            except:
                block_number = 0
        elif not isinstance(block_number, int):
            block_number = 0
        
        # Отримуємо hash
        tx_hash = tx.get('txid') or tx.get('hash') or ''
        
        # Отримуємо адреси
        tx_address = tx.get('address', '')
        # У webhook history може не бути явних полів from/to, але є address (наш гаманець)
        
        return {
            'hash': tx_hash,
            'from': '',  # У webhook history може не бути явного поля from
            'to': tx_address,  # Адреса отримувача (наш гаманець)
            'value': str(value),
            'tokenSymbol': tx.get('tokenSymbol') or 'USDT',
            'tokenDecimal': '18',
            'timeStamp': str(timestamp),
            'blockNumber': str(block_number),
            'contractAddress': tx.get('tokenAddress') or USDT_CONTRACT_BSC
        }
    
    def _format_tokenview_transaction(self, tx: Dict) -> Dict:
        """Форматування транзакції з TokenView API у стандартний формат"""
        # Отримуємо значення (може бути в різних полях)
        value_str = tx.get('value') or tx.get('amount') or tx.get('token_value') or '0'
        if isinstance(value_str, str):
            # Може бути в hex або десятковому форматі
            if value_str.startswith('0x'):
                value = int(value_str, 16)
            else:
                try:
                    # Може бути вже в правильному форматі (wei)
                    value = int(float(value_str))
                except:
                    value = 0
        else:
            value = int(value_str) if isinstance(value_str, (int, float)) else 0
        
        # Отримуємо decimals
        decimals = int(tx.get('tokenDecimal') or tx.get('decimal') or 18)
        
        # Отримуємо timestamp
        timestamp = tx.get('time') or tx.get('timestamp') or tx.get('timeStamp')
        if isinstance(timestamp, str):
            try:
                timestamp = int(timestamp)
            except:
                timestamp = 0
        elif not isinstance(timestamp, int):
            timestamp = 0
        
        # Отримуємо block number (TokenView використовує block_no)
        block_number = tx.get('block_no') or tx.get('blockHeight') or tx.get('blockNo') or tx.get('blockNumber') or '0'
        if isinstance(block_number, str):
            try:
                block_number = int(block_number)
            except:
                block_number = 0
        elif not isinstance(block_number, int):
            block_number = 0
        
        # Отримуємо hash (TokenView використовує txid)
        tx_hash = tx.get('txid') or tx.get('hash') or ''
        
        return {
            'hash': tx_hash,
            'from': tx.get('from', ''),
            'to': tx.get('to', ''),
            'value': str(value),
            'tokenSymbol': tx.get('tokenSymbol') or tx.get('symbol') or 'USDT',
            'tokenDecimal': str(decimals),
            'timeStamp': str(timestamp),
            'blockNumber': str(block_number),
            'contractAddress': tx.get('contract') or tx.get('contractAddress') or USDT_CONTRACT_BSC
        }
    
    def get_latest_block(self) -> Optional[int]:
        """Отримання останнього блоку через TokenView API"""
        try:
            # TokenView API endpoint для отримання останнього блоку
            endpoint = "block/latest/bsc"
            data = self._make_api_request(endpoint)
            
            if data and isinstance(data, dict):
                block_number = data.get('blockNo') or data.get('blockHeight') or data.get('number')
                if block_number:
                    return int(block_number)
            elif isinstance(data, list) and len(data) > 0:
                # Може повертатися список
                block_number = data[0].get('blockNo') or data[0].get('blockHeight') or data[0].get('number')
                if block_number:
                    return int(block_number)
        except Exception as e:
            print(f"Помилка отримання останнього блоку через TokenView: {e}")
        
        # Fallback через публічні RPC endpoints
        try:
            from web3 import Web3
            rpc_url = "https://bsc-dataseed.binance.org/"
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                return w3.eth.block_number
        except:
            pass
        
        return None
    
    def get_transaction_details(self, tx_hash: str) -> Optional[Dict]:
        """Отримання деталей транзакції через TokenView API"""
        try:
            endpoint = f"tx/bsc/{tx_hash}"
            return self._make_api_request(endpoint)
        except Exception as e:
            print(f"Помилка отримання деталей транзакції: {e}")
            return None
    
    def format_transaction(self, tx: Dict) -> Dict:
        """Форматування транзакції для відображення"""
        # Визначаємо, чи це вхідна транзакція
        is_incoming = tx.get('to', '').lower() == WALLET_ADDRESS.lower()
        
        # Отримуємо символ токену
        token_symbol = tx.get('tokenSymbol', 'TOKEN')
        
        # Конвертуємо значення
        value_str = tx.get('value', '0')
        try:
            value = int(value_str)
        except (ValueError, TypeError):
            value = 0
        
        decimals = int(tx.get('tokenDecimal', 18))
        amount = value / (10 ** decimals)
        
        # Конвертуємо timestamp
        timestamp = int(tx.get('timeStamp', 0))
        from datetime import datetime
        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp > 0 else "N/A"
        
        return {
            'hash': tx.get('hash', ''),
            'amount': amount,
            'symbol': token_symbol,
            'from_address': tx.get('from', ''),
            'to_address': tx.get('to', ''),
            'timestamp': time_str,
            'is_incoming': is_incoming,
            'contract_address': tx.get('contractAddress', ''),
            'block_number': tx.get('blockNumber', '')
        }
