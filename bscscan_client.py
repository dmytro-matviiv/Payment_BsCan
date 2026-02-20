"""
Модуль для роботи з BSC через QuickNode RPC Endpoint
Простий і надійний підхід для моніторингу USDT транзакцій
"""
import time
from web3 import Web3
from typing import List, Dict, Optional
from config import (
    WALLET_ADDRESS, QUICKNODE_BSC_NODE, GETBLOCK_BSC_NODE,
    REQUEST_DELAY, MAX_RETRIES, RETRY_BASE_DELAY, MAX_RETRY_DELAY,
    INITIAL_CONNECTION_DELAY, USE_FALLBACK_ENDPOINT, RATE_LIMIT_COOLDOWN,
    MAX_BLOCKS_PER_CHECK
)

# USDT контракт на BSC
USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"

# ERC20 Transfer event signature
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class BSCscanClient:
    """Клієнт для роботи з BSC через QuickNode RPC Endpoint"""
    
    def __init__(self, rpc_url: str = None, use_fallback: bool = True):
        self.use_fallback = use_fallback and USE_FALLBACK_ENDPOINT
        self.fallback_url = GETBLOCK_BSC_NODE if self.use_fallback else None
        self.rate_limit_count = 0  # Лічильник rate limit помилок
        self.dynamic_delay = REQUEST_DELAY  # Динамічна затримка, яка збільшується при rate limits
        
        if rpc_url:
            self.rpc_url = rpc_url
        else:
            self.rpc_url = QUICKNODE_BSC_NODE
        
        if not self.rpc_url:
            raise ValueError("QUICKNODE_BSC_NODE не встановлено в config.py!")
        
        # Нормалізуємо URL (прибираємо зайвий слеш в кінці, якщо є)
        self.rpc_url = self.rpc_url.rstrip('/')
        
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.wallet_address = Web3.to_checksum_address(WALLET_ADDRESS)
        self.usdt_contract = Web3.to_checksum_address(USDT_CONTRACT_BSC)
        
        # Затримка перед першою спробою підключення (якщо було багато 429)
        if INITIAL_CONNECTION_DELAY > 0:
            print(f"⏳ Очікування {INITIAL_CONNECTION_DELAY} сек перед підключенням...")
            time.sleep(INITIAL_CONNECTION_DELAY)
        
        # Перевірка підключення з retry логікою та fallback
        self._verify_connection()
    
    def _verify_connection(self):
        """Перевірка підключення з retry логікою та fallback на резервний endpoint"""
        print(f"🔌 Підключення до QuickNode: {self.rpc_url[:50]}...")
        try:
            # Спробуємо отримати поточний блок - це найнадійніший спосіб перевірити підключення
            current_block = self._retry_request(lambda: self.w3.eth.block_number)
            
            if current_block is None:
                raise ConnectionError(f"Не вдалося отримати блок від QuickNode: {self.rpc_url}")
            
            print(f"✅ Підключено до QuickNode BSC")
            print(f"   Поточний блок: {current_block}")
        except Exception as e:
            error_msg = str(e)
            
            # Якщо є резервний endpoint, спробуємо його
            if self.use_fallback and self.fallback_url:
                print(f"⚠️ QuickNode недоступний, спробуємо резервний endpoint...")
                try:
                    # Переключаємося на резервний endpoint
                    self.rpc_url = self.fallback_url.rstrip('/')
                    self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                    
                    # Спробуємо підключитися до резервного endpoint
                    current_block = self._retry_request(lambda: self.w3.eth.block_number)
                    
                    if current_block is not None:
                        print(f"✅ Підключено до резервного endpoint (GetBlock)")
                        print(f"   Поточний блок: {current_block}")
                        return
                except Exception as fallback_error:
                    print(f"❌ Резервний endpoint також недоступний: {fallback_error}")
            
            # Якщо це вже ConnectionError, просто перекидаємо його
            if isinstance(e, ConnectionError):
                raise
            # Інакше обгортаємо в ConnectionError
            raise ConnectionError(f"Не вдалося підключитися до QuickNode: {self.rpc_url}. Помилка: {error_msg}") from e
    
    def _retry_request(self, func, *args, **kwargs):
        """Виконання запиту з retry логікою для обробки 429 помилок та тимчасових помилок підключення"""
        for attempt in range(MAX_RETRIES):
            try:
                result = func(*args, **kwargs)
                # Якщо запит успішний, трохи зменшуємо динамічну затримку (але не нижче базової)
                if self.rate_limit_count > 0 and attempt == 0:
                    # Після успішного запиту після rate limit, зменшуємо затримку
                    self.dynamic_delay = max(self.dynamic_delay * 0.9, REQUEST_DELAY)
                return result
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "429" in error_str or "too many requests" in error_str
                # Також обробляємо інші тимчасові помилки підключення
                is_connection_error = (
                    "connection" in error_str or 
                    "timeout" in error_str or
                    "network" in error_str or
                    "temporarily unavailable" in error_str
                )
                # Обробляємо помилки про занадто багато результатів (413, query too large тощо)
                is_query_too_large = (
                    "413" in error_str or
                    "query returned more than" in error_str or
                    "too large" in error_str or
                    "query size" in error_str
                )
                
                # Retry для rate limit та тимчасових помилок підключення
                # Для помилок "query too large" не робимо retry - просто пропускаємо
                should_retry = (is_rate_limit or is_connection_error) and attempt < MAX_RETRIES - 1
                
                if is_query_too_large:
                    # Для помилок "query too large" не робимо retry - просто повертаємо None
                    print(f"⚠️ Запит занадто великий для блоку (413/query too large), пропускаємо...")
                    return None
                
                if not should_retry:
                    # Якщо це не тимчасова помилка або остання спроба, викидаємо помилку
                    raise
                
                # Експоненційний backoff з базовою затримкою
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                if is_rate_limit:
                    self.rate_limit_count += 1
                    # Для першої 429 помилки одразу додаємо cooldown
                    if attempt == 0:
                        delay = RATE_LIMIT_COOLDOWN
                        print(f"⚠️ Rate limit (429) виявлено! Очікування {delay:.1f} сек перед повторною спробою...")
                    else:
                        print(f"⚠️ Rate limit (429). Спробa {attempt + 1}/{MAX_RETRIES}. Очікування {delay:.1f} сек...")
                    
                    # Для 429 помилок додаємо додаткову затримку після кількох спроб
                    if attempt >= 2:  # Після 2 спроб додаємо ще 60 секунд
                        delay += 60
                        print(f"   Додаткова затримка через багато 429 помилок: +60 сек")
                    
                    # Збільшуємо динамічну затримку між запитами
                    self.dynamic_delay = min(self.dynamic_delay * 1.5, 10.0)
                else:
                    print(f"⚠️ Помилка підключення. Спробa {attempt + 1}/{MAX_RETRIES}. Очікування {delay:.1f} сек...")
                time.sleep(delay)
        
        return None
    
    def get_latest_block(self) -> Optional[int]:
        """Отримання останнього блоку з retry логікою"""
        try:
            return self._retry_request(lambda: self.w3.eth.block_number)
        except Exception as e:
            print(f"❌ Помилка отримання блоку: {e}")
            return None
    
    def get_token_transactions(self, address: str = WALLET_ADDRESS, start_block: int = 0, 
                               end_block: int = 99999999) -> List[Dict]:
        """Отримання USDT транзакцій для адреси"""
        # Обмежуємо діапазон блоків (максимум MAX_BLOCKS_PER_CHECK блоків за раз для економії API credits)
        latest = self.get_latest_block()
        if not latest:
            return []
        
        if end_block > latest:
            end_block = latest
        
        if start_block < 0:
            start_block = 0
        
        block_range = end_block - start_block + 1
        if block_range > MAX_BLOCKS_PER_CHECK:
            # Якщо діапазон занадто великий, перевіряємо тільки останні MAX_BLOCKS_PER_CHECK блоків
            start_block = max(0, end_block - (MAX_BLOCKS_PER_CHECK - 1))
            block_range = MAX_BLOCKS_PER_CHECK
        
        # Перевіряємо блоки по одному для надійності
        all_transactions = []
        address_checksum = Web3.to_checksum_address(address)
        blocks_checked = 0
        blocks_with_logs = 0
        block_cache = {}  # Кеш для блоків (щоб не запитувати один блок кілька разів)
        
        print(f"🔍 Пошук USDT транзакцій в блоках {start_block}-{end_block} ({block_range} блоків)")
        print(f"   Контракт USDT: {self.usdt_contract}")
        print(f"   Адреса гаманця: {address}")
        print(f"   Адреса (checksum): {address_checksum}")
        print(f"   Шукаємо всі USDT транзакції, потім фільтруємо по адресі")
        
        for block_num in range(start_block, end_block + 1):
            try:
                # Спочатку шукаємо ВСІ USDT транзакції в блоці (без фільтрації по адресі)
                # Це дозволяє знайти транзакції навіть якщо фільтр по адресі не працює
                filter_params_all = {
                    'fromBlock': block_num,
                    'toBlock': block_num,
                    'address': self.usdt_contract,
                    'topics': [
                        TRANSFER_EVENT_TOPIC,  # Transfer event
                        None,  # from (будь-яка)
                        None   # to (будь-яка) - шукаємо всі транзакції
                    ]
                }
                
                logs = self._retry_request(
                    lambda: self.w3.eth.get_logs(filter_params_all)
                )
                
                blocks_checked += 1
                
                # Обробляємо знайдені логи (якщо retry успішний)
                if logs is not None:
                    # Перевіряємо, чи logs є списком
                    if not isinstance(logs, list):
                        print(f"      ⚠️ Блок {block_num}: отримано некоректний тип даних (очікувався список)")
                        continue
                    
                    if len(logs) > 0:
                        blocks_with_logs += 1
                        print(f"   📦 Блок {block_num}: знайдено {len(logs)} USDT логів")
                    
                    # Отримуємо timestamp блоку один раз (кешуємо)
                    if block_num not in block_cache:
                        try:
                            block = self._retry_request(lambda: self.w3.eth.get_block(block_num, full_transactions=False))
                            block_cache[block_num] = block.get('timestamp', 0) if block else 0
                        except Exception as block_error:
                            block_cache[block_num] = 0
                    
                    block_timestamp = block_cache[block_num]
                    
                    # Фільтруємо логи по нашій адресі (як отримувача)
                    for log in logs:
                        try:
                            # Перевіряємо, чи log є словником
                            if not isinstance(log, dict):
                                continue
                            
                            tx = self._log_to_transaction(log, block_num, block_timestamp)
                            if tx:
                                # Перевіряємо, чи це транзакція на нашу адресу
                                tx_to = tx.get('to', '').lower()
                                tx_from = tx.get('from', '').lower()
                                
                                # Перевіряємо, чи адреси не порожні
                                if not tx_to or not tx_from:
                                    continue
                                
                                # Порівнюємо адреси (case-insensitive)
                                if tx_to == address_checksum.lower():
                                    all_transactions.append(tx)
                                    print(f"      ✅ Знайдено ВХІДНУ транзакцію:")
                                    print(f"         Hash: {tx.get('hash', '')}")
                                    print(f"         From: {tx_from}")
                                    print(f"         To: {tx_to}")
                                    print(f"         Value: {tx.get('value', '0')}")
                                elif tx_from == address_checksum.lower():
                                    # Це вихідна транзакція, не додаємо її
                                    pass
                        except Exception as log_error:
                            # Пропускаємо пошкоджені логи, щоб не зупиняти обробку
                            error_str = str(log_error).lower()
                            # Не виводимо помилки для типових проблем (некоректні формати даних тощо)
                            if "index" not in error_str and "out of range" not in error_str and "none" not in error_str:
                                print(f"      ⚠️ Помилка обробки логу в блоці {block_num}: {log_error}")
                            continue
                
                # Затримка між запитами для уникнення rate limiting (використовуємо динамічну затримку)
                if block_num < end_block:
                    # Якщо знайдено багато логів, збільшуємо затримку
                    if logs and len(logs) > 20:
                        delay = self.dynamic_delay * 2  # Подвоюємо затримку для блоків з багатьма логами
                        print(f"      ⏳ Багато логів ({len(logs)}), затримка {delay:.1f} сек...")
                        time.sleep(delay)
                    elif self.dynamic_delay > 0:
                        time.sleep(self.dynamic_delay)
                
            except Exception as e:
                # Якщо помилка 413 або подібна, просто пропускаємо блок
                error_str = str(e).lower()
                if "413" not in error_str and "too large" not in error_str:
                    # Для 429 помилок вже виведено повідомлення в _retry_request
                    if "429" not in error_str and "too many requests" not in error_str:
                        print(f"⚠️ Помилка блоку {block_num}: {e}")
                continue
        
        print(f"✅ Перевірено {blocks_checked} блоків")
        print(f"   Блоків з логами: {blocks_with_logs}")
        print(f"✅ Знайдено {len(all_transactions)} транзакцій USDT")
        
        if len(all_transactions) == 0 and blocks_checked > 0:
            print(f"⚠️ Транзакції USDT не знайдено в перевірених блоках")
            print(f"   Можливі причини:")
            print(f"   - В цих блоках немає USDT транзакцій на адресу {address}")
            print(f"   - Транзакції можуть бути в старіших блоках")
            print(f"   - Проблеми з API через rate limiting")
        
        return all_transactions
    
    def _address_to_topic(self, address: str) -> str:
        """Конвертація адреси в topic (32 байти, padded зліва нулями)"""
        addr = address[2:] if address.startswith('0x') else address
        return '0x' + addr.lower().zfill(64)
    
    def _log_to_transaction(self, log: Dict, block_number: int, timestamp: int = 0) -> Optional[Dict]:
        """Конвертація логу Transfer event в транзакцію"""
        try:
            # Перевірка наявності логу
            if not log or not isinstance(log, dict):
                return None
            
            # Отримуємо адреси з topics
            topics = log.get('topics', [])
            if not topics or len(topics) < 3:
                return None
            
            # Перевіряємо, чи topics не None
            if topics[1] is None or topics[2] is None:
                return None
            
            # Конвертуємо topics в рядки
            try:
                topic1 = topics[1].hex() if hasattr(topics[1], 'hex') else str(topics[1])
                topic2 = topics[2].hex() if hasattr(topics[2], 'hex') else str(topics[2])
            except (AttributeError, IndexError, TypeError) as e:
                return None
            
            # Перевіряємо формат topics
            if not topic1 or not topic2:
                return None
            
            # Витягуємо адреси з topics (останні 40 символів після '0x')
            # Topics мають формат: 0x + 24 нулі + 40 символів адреси
            try:
                # Нормалізуємо topic (прибираємо 0x якщо є, додаємо якщо немає)
                topic1_clean = topic1.replace('0x', '').zfill(64)
                topic2_clean = topic2.replace('0x', '').zfill(64)
                
                # Беремо останні 40 символів (адреса)
                from_addr_raw = topic1_clean[-40:] if len(topic1_clean) >= 40 else topic1_clean
                to_addr_raw = topic2_clean[-40:] if len(topic2_clean) >= 40 else topic2_clean
                
                # Перевіряємо, чи адреси мають правильну довжину
                if len(from_addr_raw) != 40 or len(to_addr_raw) != 40:
                    return None
                
                from_addr = '0x' + from_addr_raw.lower()
                to_addr = '0x' + to_addr_raw.lower()
            except (ValueError, IndexError, TypeError) as e:
                return None
            
            # Отримуємо value з data
            try:
                data = log.get('data', '0x0')
                if hasattr(data, 'hex'):
                    value_hex = data.hex()
                else:
                    value_hex = data if isinstance(data, str) else '0x0'
                
                # Перевіряємо формат value_hex
                if not value_hex or value_hex == '0x':
                    value = 0
                else:
                    value = int(value_hex, 16)
            except (ValueError, TypeError) as e:
                value = 0
            
            # Отримуємо transaction hash
            try:
                tx_hash = log.get('transactionHash', '')
                if not tx_hash:
                    return None
                
                if hasattr(tx_hash, 'hex'):
                    tx_hash = tx_hash.hex()
                elif not isinstance(tx_hash, str):
                    tx_hash = str(tx_hash)
                
                # Перевіряємо формат hash
                if not tx_hash or len(tx_hash) < 10:
                    return None
            except (AttributeError, TypeError) as e:
                return None
            
            # Використовуємо переданий timestamp (не робимо додатковий запит)
            return {
                'hash': tx_hash,
                'from': from_addr,
                'to': to_addr,
                'value': str(value),
                'tokenSymbol': 'USDT',
                'tokenDecimal': '18',
                'timeStamp': str(timestamp),
                'blockNumber': str(block_number),
                'contractAddress': self.usdt_contract
            }
        except Exception as e:
            # Не виводимо помилку для кожного некоректного логу (їх може бути багато)
            # Помилка буде оброблена на вищому рівні
            return None
    
    def format_transaction(self, tx: Dict) -> Dict:
        """Форматування транзакції для відображення"""
        is_incoming = tx.get('to', '').lower() == WALLET_ADDRESS.lower()
        
        value_str = tx.get('value', '0')
        try:
            value = int(value_str)
        except (ValueError, TypeError):
            value = 0
        
        decimals = int(tx.get('tokenDecimal', 18))
        amount = value / (10 ** decimals)
        
        timestamp = int(tx.get('timeStamp', 0))
        from datetime import datetime
        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp > 0 else "N/A"
        
        return {
            'hash': tx.get('hash', ''),
            'amount': amount,
            'symbol': tx.get('tokenSymbol', 'USDT'),
            'from_address': tx.get('from', ''),
            'to_address': tx.get('to', ''),
            'timestamp': time_str,
            'is_incoming': is_incoming,
            'contract_address': tx.get('contractAddress', ''),
            'block_number': tx.get('blockNumber', '')
        }
    
    def check_transaction_by_hash(self, tx_hash: str) -> Optional[Dict]:
        """Перевірка конкретної транзакції за хешем"""
        try:
            receipt = self._retry_request(lambda: self.w3.eth.get_transaction_receipt(tx_hash))
            if not receipt:
                return None
            block = self._retry_request(lambda: self.w3.eth.get_block(receipt['blockNumber']))
            if not block:
                return None
            timestamp = block['timestamp']
            
            address_checksum = Web3.to_checksum_address(WALLET_ADDRESS)
            
            for log in receipt['logs']:
                log_addr = log['address']
                if hasattr(log_addr, 'hex'):
                    log_addr = log_addr.hex()
                if not isinstance(log_addr, str):
                    log_addr = str(log_addr)
                
                if log_addr.lower() != self.usdt_contract.lower():
                    continue
                
                if len(log['topics']) < 3:
                    continue
                
                topic0 = log['topics'][0]
                if hasattr(topic0, 'hex'):
                    topic0 = topic0.hex()
                if topic0.lower() != TRANSFER_EVENT_TOPIC.lower():
                    continue
                
                topic1 = log['topics'][1]
                topic2 = log['topics'][2]
                if hasattr(topic1, 'hex'):
                    topic1 = topic1.hex()
                if hasattr(topic2, 'hex'):
                    topic2 = topic2.hex()
                
                from_addr = '0x' + (topic1[-40:] if len(topic1) >= 40 else topic1.zfill(64)[-40:])
                to_addr = '0x' + (topic2[-40:] if len(topic2) >= 40 else topic2.zfill(64)[-40:])
                
                if to_addr.lower() != address_checksum.lower():
                    continue
                
                data = log['data']
                if hasattr(data, 'hex'):
                    value_hex = data.hex()
                else:
                    value_hex = data if isinstance(data, str) else '0x'
                value = int(value_hex, 16) if value_hex != '0x' and value_hex else 0
                
                return {
                    'hash': tx_hash,
                    'from': from_addr,
                    'to': to_addr,
                    'value': str(value),
                    'tokenSymbol': 'USDT',
                    'tokenDecimal': '18',
                    'timeStamp': str(timestamp),
                    'blockNumber': str(receipt['blockNumber']),
                    'contractAddress': self.usdt_contract
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Помилка перевірки транзакції: {e}")
            import traceback
            traceback.print_exc()
            return None
