"""
Тестовий скрипт для перевірки конкретної транзакції
"""
from web3 import Web3
from bscscan_client import BSCscanClient
from telegram_bot import TelegramBot
from config import QUICKNODE_BSC_NODE, WALLET_ADDRESS

# USDT контракт на BSC
USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"

# Транзакція для перевірки
TX_HASH = "0xc76a2b45c012aadc0fb56bb4f64621e9818598296548b5a9a1b0034e14133eae"

def check_transaction():
    """Перевірка конкретної транзакції"""
    print("=" * 60)
    print("ПЕРЕВІРКА ТРАНЗАКЦІЇ")
    print("=" * 60)
    print(f"Хеш транзакції: {TX_HASH}")
    print(f"Адреса гаманця: {WALLET_ADDRESS}")
    print("=" * 60)
    
    # Підключаємося до QuickNode
    w3 = Web3(Web3.HTTPProvider(QUICKNODE_BSC_NODE))
    
    if not w3.is_connected():
        print("❌ Не вдалося підключитися до QuickNode")
        return
    
    print("✅ Підключено до QuickNode")
    
    try:
        # Отримуємо receipt транзакції
        tx_receipt = w3.eth.get_transaction_receipt(TX_HASH)
        print(f"✅ Транзакція знайдена!")
        print(f"   Блок: {tx_receipt['blockNumber']}")
        print(f"   Статус: {'Успішно' if tx_receipt['status'] == 1 else 'Помилка'}")
        
        # Перевіряємо логи (Transfer events)
        print(f"\n📋 Перевірка Transfer events...")
        print(f"   Знайдено {len(tx_receipt['logs'])} логів")
        
        # Шукаємо USDT Transfer events
        usdt_transfers = []
        for log in tx_receipt['logs']:
            # Перевіряємо, чи це USDT контракт
            if log['address'].lower() == USDT_CONTRACT_BSC.lower():
                # Перевіряємо, чи це Transfer event
                if len(log['topics']) >= 3:
                    # Topic[0] = Transfer event signature
                    # Topic[1] = from address
                    # Topic[2] = to address
                    from_addr = '0x' + log['topics'][1][-40:] if len(log['topics']) > 1 else ''
                    to_addr = '0x' + log['topics'][2][-40:] if len(log['topics']) > 2 else ''
                    
                    # Отримуємо value
                    value_hex = log['data']
                    value = int(value_hex, 16) if value_hex != '0x' else 0
                    amount = value / (10 ** 18)  # USDT має 18 decimals
                    
                    print(f"\n   💰 USDT Transfer знайдено:")
                    print(f"      Від: {from_addr}")
                    print(f"      До: {to_addr}")
                    print(f"      Сума: {amount:.2f} USDT")
                    
                    # Перевіряємо, чи це наша адреса
                    if to_addr.lower() == WALLET_ADDRESS.lower():
                        print(f"      ✅ Це вхідна транзакція на нашу адресу!")
                        usdt_transfers.append({
                            'from': from_addr,
                            'to': to_addr,
                            'amount': amount,
                            'hash': TX_HASH,
                            'block': tx_receipt['blockNumber']
                        })
                    else:
                        print(f"      ⚠️ Це не наша адреса")
        
        if usdt_transfers:
            print(f"\n✅ Знайдено {len(usdt_transfers)} вхідних транзакцій USDT!")
            
            # Тестуємо відправку в Telegram
            print(f"\n📱 Тестування відправки в Telegram...")
            telegram = TelegramBot()
            
            for transfer in usdt_transfers:
                # Отримуємо timestamp блоку
                block = w3.eth.get_block(tx_receipt['blockNumber'])
                timestamp = block['timestamp']
                
                from datetime import datetime
                time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                
                tx_data = {
                    'hash': TX_HASH,
                    'amount': transfer['amount'],
                    'symbol': 'USDT',
                    'from_address': transfer['from'],
                    'to_address': transfer['to'],
                    'timestamp': time_str,
                    'is_incoming': True,
                    'contract_address': USDT_CONTRACT_BSC,
                    'block_number': str(transfer['block'])
                }
                
                if telegram.send_payment_notification(tx_data):
                    print(f"   ✅ Повідомлення надіслано успішно!")
                else:
                    print(f"   ❌ Помилка надсилання повідомлення")
        else:
            print(f"\n⚠️ Не знайдено вхідних транзакцій USDT на адресу {WALLET_ADDRESS}")
            
    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_transaction()
