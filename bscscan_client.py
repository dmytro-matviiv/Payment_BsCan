"""
Модуль для роботи з BSC через QuickNode RPC Endpoint
Використовує Web3.py для моніторингу транзакцій через eth_getLogs
"""
from web3 import Web3
from typing import List, Dict, Optional
from config import WALLET_ADDRESS, QUICKNODE_BSC_NODE

# USDT контракт на BSC
USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"

# ERC20 Transfer event signature (keccak256 hash of "Transfer(address,address,uint256)")
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class BSCscanClient:
    """Клієнт для роботи з BSC через QuickNode RPC Endpoint"""
    
    def __init__(self, rpc_url: str = None):
        # Використовуємо QuickNode RPC endpoint з конфігурації
        if rpc_url:
            self.rpc_url = rpc_url
        else:
            self.rpc_url = QUICKNODE_BSC_NODE
        
        if not self.rpc_url:
            raise ValueError(
                "QUICKNODE_BSC_NODE не встановлено в config.py!\n"
                "Отримайте endpoint на https://dashboard.quicknode.com/endpoints/new/bsc\n"
                "Виберіть Mainnet та скопіюйте HTTPS URL в config.py"
            )
        
        # Ініціалізуємо Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Перевіряємо підключення
        if not self.w3.is_connected():
            raise ConnectionError(f"Не вдалося підключитися до QuickNode RPC: {self.rpc_url}")
        
        print(f"✅ Підключено до QuickNode BSC RPC: {self.rpc_url[:50]}...")
        print(f"✅ Поточний блок: {self.w3.eth.block_number}")
        
        # Конвертуємо адреси в checksum format
        self.wallet_address = Web3.to_checksum_address(WALLET_ADDRESS)
        self.usdt_contract = Web3.to_checksum_address(USDT_CONTRACT_BSC)
        
        self.last_block = None
    
    def get_latest_block(self) -> Optional[int]:
        """Отримання останнього блоку через QuickNode RPC"""
        try:
            return self.w3.eth.block_number
        except Exception as e:
            print(f"Помилка отримання останнього блоку: {e}")
            return None
    
    def get_token_transactions(self, address: str = WALLET_ADDRESS, start_block: int = 0, 
                               end_block: int = 99999999) -> List[Dict]:
        """Отримання токен транзакцій для адреси через QuickNode RPC"""
        return self._get_token_transactions_via_rpc(address, start_block, end_block)
    
    def _get_token_transactions_via_rpc(self, address: str, start_block: int, end_block: int, 
                                       skip_range_check: bool = False) -> List[Dict]:
        """Отримання транзакцій токенів через QuickNode RPC використовуючи eth_getLogs"""
        # Завжди перевіряємо блоки по одному для надійності
        if not skip_range_check:
            block_range = end_block - start_block + 1
            if block_range > 1:
                # Розбиваємо на окремі блоки
                return self._get_token_transactions_in_chunks(address, start_block, end_block, 1)
        
        # Конвертуємо адресу в checksum format
        address_checksum = Web3.to_checksum_address(address)
        
        # Формуємо фільтр для Transfer events (тільки один блок)
        filter_params = {
            'fromBlock': start_block,
            'toBlock': start_block,  # Тільки один блок
            'address': self.usdt_contract,  # USDT контракт
            'topics': [
                TRANSFER_EVENT_TOPIC,  # Transfer event
                None,  # from (будь-яка адреса)
                [self._address_to_topic(address_checksum)]  # to = наша адреса
            ]
        }
        
        try:
            # Отримуємо логи через eth_getLogs
            logs = self.w3.eth.get_logs(filter_params)
            
            # Конвертуємо логи в транзакції
            transactions = []
            for log in logs:
                try:
                    tx = self._log_to_transaction(log)
                    if tx:
                        transactions.append(tx)
                except Exception as e:
                    print(f"⚠️ Помилка обробки логу в блоці {start_block}: {e}")
                    continue
            
            if transactions:
                print(f"✅ Блок {start_block}: знайдено {len(transactions)} транзакцій USDT")
            return transactions
            
        except Exception as e:
            error_str = str(e).lower()
            # Якщо навіть один блок занадто великий, пропускаємо його
            if ("413" in error_str or "request entity too large" in error_str):
                print(f"⚠️ Блок {start_block} пропущено - занадто багато USDT транзакцій (це нормально для BSC)")
            else:
                print(f"⚠️ Помилка при перевірці блоку {start_block}: {e}")
            return []
    
    def _get_token_transactions_in_chunks(self, address: str, start_block: int, end_block: int, 
                                          chunk_size: int = 1) -> List[Dict]:
        """Отримання транзакцій частинами, перевіряючи блоки по одному"""
        all_transactions = []
        current_block = start_block
        total_blocks = end_block - start_block + 1
        
        print(f"📊 Перевірка {total_blocks} блоків (по одному для надійності)...")
        
        while current_block <= end_block:
            try:
                # Перевіряємо один блок
                chunk_txs = self._get_token_transactions_via_rpc(address, current_block, current_block, skip_range_check=True)
                all_transactions.extend(chunk_txs)
            except Exception as e:
                print(f"⚠️ Помилка при перевірці блоку {current_block}: {e}")
            
            current_block += 1
            
            # Невелика затримка між запитами
            import time
            time.sleep(0.1)
        
        print(f"✅ Перевірка завершена. Знайдено {len(all_transactions)} транзакцій USDT")
        return all_transactions
    
    def _address_to_topic(self, address: str) -> str:
        """Конвертація адреси в topic (32 байти, padded зліва нулями)"""
        # Видаляємо '0x' якщо є
        addr = address[2:] if address.startswith('0x') else address
        # Додаємо padding зліва до 64 символів (32 байти)
        return '0x' + addr.lower().zfill(64)
    
    def _log_to_transaction(self, log: Dict) -> Optional[Dict]:
        """Конвертація логу Transfer event в транзакцію"""
        try:
            # Отримуємо дані з логу
            # topics[0] = Transfer event signature
            # topics[1] = from address
            # topics[2] = to address
            # data = value (uint256)
            
            topics = log.get('topics', [])
            if len(topics) < 3:
                return None
            
            from_address = '0x' + topics[1][-40:]  # Останні 40 символів (20 байт адреси)
            to_address = '0x' + topics[2][-40:]
            
            # Отримуємо value з data
            value_hex = log.get('data', '0x0')
            value = int(value_hex, 16) if value_hex != '0x' else 0
            
            # Отримуємо інформацію про транзакцію
            tx_hash = log.get('transactionHash', '').hex() if hasattr(log.get('transactionHash'), 'hex') else log.get('transactionHash', '')
            block_number = log.get('blockNumber', 0)
            
            # Отримуємо timestamp з блоку
            try:
                block = self.w3.eth.get_block(block_number)
                timestamp = block.get('timestamp', 0)
            except:
                timestamp = 0
            
            return {
                'hash': tx_hash,
                'from': from_address,
                'to': to_address,
                'value': str(value),
                'tokenSymbol': 'USDT',
                'tokenDecimal': '18',
                'timeStamp': str(timestamp),
                'blockNumber': str(block_number),
                'contractAddress': self.usdt_contract
            }
        except Exception as e:
            print(f"Помилка конвертації логу: {e}")
            return None
    
    def get_transaction_details(self, tx_hash: str) -> Optional[Dict]:
        """Отримання деталей транзакції через QuickNode RPC"""
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return {
                'transaction': dict(tx),
                'receipt': dict(receipt)
            }
        except Exception as e:
            print(f"Помилка отримання деталей транзакції: {e}")
            return None
    
    def check_transaction_by_hash(self, tx_hash: str) -> Optional[Dict]:
        """Перевірка конкретної транзакції за хешем та отримання USDT Transfer events"""
        try:
            # Отримуємо receipt транзакції
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            # Отримуємо блок для timestamp
            block = self.w3.eth.get_block(receipt['blockNumber'])
            timestamp = block['timestamp']
            
            # Шукаємо USDT Transfer events
            address_checksum = Web3.to_checksum_address(WALLET_ADDRESS)
            
            for log in receipt['logs']:
                # Перевіряємо, чи це USDT контракт
                log_address = log['address']
                if isinstance(log_address, bytes):
                    log_address = log_address.hex()
                if not isinstance(log_address, str):
                    log_address = str(log_address)
                if log_address.lower() != self.usdt_contract.lower():
                    continue
                
                # Перевіряємо, чи це Transfer event
                if len(log['topics']) < 3:
                    continue
                
                # Перевіряємо event signature (topic[0])
                topic0 = log['topics'][0]
                if hasattr(topic0, 'hex'):
                    topic0 = topic0.hex()
                if topic0.lower() != TRANSFER_EVENT_TOPIC.lower():
                    continue
                
                # Отримуємо адреси
                topic1 = log['topics'][1]
                topic2 = log['topics'][2]
                if hasattr(topic1, 'hex'):
                    topic1 = topic1.hex()
                if hasattr(topic2, 'hex'):
                    topic2 = topic2.hex()
                
                from_addr = '0x' + (topic1[-40:] if len(topic1) >= 40 else topic1.zfill(64)[-40:])
                to_addr = '0x' + (topic2[-40:] if len(topic2) >= 40 else topic2.zfill(64)[-40:])
                
                # Перевіряємо, чи це наша адреса
                if to_addr.lower() != address_checksum.lower():
                    continue
                
                # Отримуємо value
                data = log['data']
                if hasattr(data, 'hex'):
                    value_hex = data.hex()
                else:
                    value_hex = data if isinstance(data, str) else '0x'
                value = int(value_hex, 16) if value_hex != '0x' and value_hex else 0
                
                # Форматуємо транзакцію
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
            print(f"Помилка перевірки транзакції {tx_hash}: {e}")
            import traceback
            traceback.print_exc()
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
