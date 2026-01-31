"""
Модуль для роботи з BSC через QuickNode RPC Endpoint
Простий і надійний підхід для моніторингу USDT транзакцій
"""
from web3 import Web3
from typing import List, Dict, Optional
from config import WALLET_ADDRESS, QUICKNODE_BSC_NODE

# USDT контракт на BSC
USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"

# ERC20 Transfer event signature
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class BSCscanClient:
    """Клієнт для роботи з BSC через QuickNode RPC Endpoint"""
    
    def __init__(self, rpc_url: str = None):
        if rpc_url:
            self.rpc_url = rpc_url
        else:
            self.rpc_url = QUICKNODE_BSC_NODE
        
        if not self.rpc_url:
            raise ValueError("QUICKNODE_BSC_NODE не встановлено в config.py!")
        
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Не вдалося підключитися до QuickNode: {self.rpc_url}")
        
        print(f"✅ Підключено до QuickNode BSC")
        print(f"   Поточний блок: {self.w3.eth.block_number}")
        
        self.wallet_address = Web3.to_checksum_address(WALLET_ADDRESS)
        self.usdt_contract = Web3.to_checksum_address(USDT_CONTRACT_BSC)
    
    def get_latest_block(self) -> Optional[int]:
        """Отримання останнього блоку"""
        try:
            return self.w3.eth.block_number
        except Exception as e:
            print(f"❌ Помилка отримання блоку: {e}")
            return None
    
    def get_token_transactions(self, address: str = WALLET_ADDRESS, start_block: int = 0, 
                               end_block: int = 99999999) -> List[Dict]:
        """Отримання USDT транзакцій для адреси"""
        # Обмежуємо діапазон блоків (максимум 50 блоків за раз)
        latest = self.get_latest_block()
        if not latest:
            return []
        
        if end_block > latest:
            end_block = latest
        
        if start_block < 0:
            start_block = 0
        
        block_range = end_block - start_block + 1
        if block_range > 50:
            # Якщо діапазон занадто великий, перевіряємо тільки останні 50 блоків
            start_block = max(0, end_block - 49)
            block_range = 50
        
        print(f"🔍 Пошук USDT транзакцій в блоках {start_block}-{end_block} ({block_range} блоків)")
        
        # Перевіряємо блоки по одному для надійності
        all_transactions = []
        address_checksum = Web3.to_checksum_address(address)
        
        for block_num in range(start_block, end_block + 1):
            try:
                # Отримуємо логи Transfer events для одного блоку
                filter_params = {
                    'fromBlock': block_num,
                    'toBlock': block_num,
                    'address': self.usdt_contract,
                    'topics': [
                        TRANSFER_EVENT_TOPIC,  # Transfer event
                        None,  # from (будь-яка)
                        [self._address_to_topic(address_checksum)]  # to = наша адреса
                    ]
                }
                
                logs = self.w3.eth.get_logs(filter_params)
                
                # Обробляємо знайдені логи
                for log in logs:
                    tx = self._log_to_transaction(log, block_num)
                    if tx:
                        all_transactions.append(tx)
                
            except Exception as e:
                # Якщо помилка 413 або подібна, просто пропускаємо блок
                error_str = str(e).lower()
                if "413" not in error_str and "too large" not in error_str:
                    print(f"⚠️ Помилка блоку {block_num}: {e}")
                continue
        
        print(f"✅ Знайдено {len(all_transactions)} транзакцій USDT")
        return all_transactions
    
    def _address_to_topic(self, address: str) -> str:
        """Конвертація адреси в topic (32 байти, padded зліва нулями)"""
        addr = address[2:] if address.startswith('0x') else address
        return '0x' + addr.lower().zfill(64)
    
    def _log_to_transaction(self, log: Dict, block_number: int) -> Optional[Dict]:
        """Конвертація логу Transfer event в транзакцію"""
        try:
            # Отримуємо адреси з topics
            topics = log.get('topics', [])
            if len(topics) < 3:
                return None
            
            # Конвертуємо topics в рядки
            topic1 = topics[1].hex() if hasattr(topics[1], 'hex') else str(topics[1])
            topic2 = topics[2].hex() if hasattr(topics[2], 'hex') else str(topics[2])
            
            from_addr = '0x' + topic1[-40:].lower()
            to_addr = '0x' + topic2[-40:].lower()
            
            # Отримуємо value з data
            data = log.get('data', '0x0')
            if hasattr(data, 'hex'):
                value_hex = data.hex()
            else:
                value_hex = data if isinstance(data, str) else '0x0'
            
            value = int(value_hex, 16) if value_hex and value_hex != '0x' else 0
            
            # Отримуємо transaction hash
            tx_hash = log.get('transactionHash', '')
            if hasattr(tx_hash, 'hex'):
                tx_hash = tx_hash.hex()
            elif not isinstance(tx_hash, str):
                tx_hash = str(tx_hash)
            
            # Отримуємо timestamp з блоку
            try:
                block = self.w3.eth.get_block(block_number)
                timestamp = block.get('timestamp', 0)
            except:
                timestamp = 0
            
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
            print(f"⚠️ Помилка обробки логу: {e}")
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
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            block = self.w3.eth.get_block(receipt['blockNumber'])
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
