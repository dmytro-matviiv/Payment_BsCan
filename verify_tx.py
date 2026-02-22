"""
Діагностика: перевіряє чи QuickNode правильно фільтрує USDT логи по адресі.
Запуск: python verify_tx.py
"""
import sys
import time
from web3 import Web3
from config import QUICKNODE_BSC_NODE, WALLET_ADDRESS, INITIAL_CONNECTION_DELAY

USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TEST_TX = "0x79a075d073e08f7b4cd0c15fb661993da9c448bea930341c942133b4fc34d8ca"
TEST_BLOCK = 82686936


def to_hex(val):
    if val is None:
        return ""
    if hasattr(val, "hex"):
        return val.hex()
    return str(val)


def address_to_topic(addr):
    raw = addr[2:] if addr.startswith("0x") else addr
    return "0x" + raw.lower().zfill(64)


def main():
    tx_hash = sys.argv[1] if len(sys.argv) > 1 else TEST_TX
    block_num = int(sys.argv[2]) if len(sys.argv) > 2 else TEST_BLOCK

    print(f"Адреса гаманця: {WALLET_ADDRESS}")
    print(f"TX хеш: {tx_hash}")
    print(f"Блок: {block_num}")
    print()

    rpc = QUICKNODE_BSC_NODE.rstrip("/")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    print(f"Підключення до {rpc[:50]}...")
    print(f"Блок: {w3.eth.block_number}")
    print()

    # -- ТЕСТ 1: Отримання receipt по хешу --
    print("=" * 60)
    print("ТЕСТ 1: get_transaction_receipt")
    print("=" * 60)
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        print(f"Receipt отримано. Блок: {receipt['blockNumber']}, логів: {len(receipt['logs'])}")
        usdt_contract_lower = USDT_CONTRACT.lower()
        wallet_lower = WALLET_ADDRESS.lower()
        for i, log in enumerate(receipt["logs"]):
            addr = to_hex(log.get("address", "")).lower()
            if usdt_contract_lower not in addr and addr.replace("0x", "") != usdt_contract_lower.replace("0x", ""):
                continue
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue
            t0 = to_hex(topics[0]).lower()
            if TRANSFER_TOPIC.lower().replace("0x", "") not in t0.replace("0x", ""):
                continue
            t1 = to_hex(topics[1])
            t2 = to_hex(topics[2])
            from_addr = "0x" + t1[-40:].lower()
            to_addr = "0x" + t2[-40:].lower()
            data = to_hex(log.get("data", "0x0"))
            value = int(data, 16) if data and data != "0x" else 0
            amount = value / 1e18
            print(f"  USDT Transfer #{i}:")
            print(f"    from: {from_addr}")
            print(f"    to:   {to_addr}")
            print(f"    amount: {amount:.2f} USDT")
            if to_addr == wallet_lower:
                print(f"    >>> ЦЕ НАШ ПЛАТІЖ! <<<")
    except Exception as e:
        print(f"Помилка: {e}")

    # -- ТЕСТ 2: get_logs БЕЗ фільтра по адресі (всі USDT в блоці) --
    print()
    print("=" * 60)
    print("ТЕСТ 2: get_logs БЕЗ фільтра по адресі (1 блок)")
    print("=" * 60)
    try:
        logs = w3.eth.get_logs({
            "fromBlock": block_num,
            "toBlock": block_num,
            "address": Web3.to_checksum_address(USDT_CONTRACT),
            "topics": [TRANSFER_TOPIC, None, None],
        })
        print(f"Отримано {len(logs)} USDT Transfer логів у блоці {block_num}")
        wallet_lower = WALLET_ADDRESS.lower()
        found = 0
        for log in logs:
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue
            to_addr = "0x" + to_hex(topics[2])[-40:].lower()
            if to_addr == wallet_lower:
                found += 1
                data = to_hex(log.get("data", "0x0"))
                value = int(data, 16) if data and data != "0x" else 0
                print(f"  ЗНАЙДЕНО! amount={value/1e18:.2f} USDT, tx={to_hex(log.get('transactionHash',''))[:20]}...")
        if found == 0:
            print(f"  Транзакцій на адресу {wallet_lower[:12]}... не знайдено серед {len(logs)} логів")
    except Exception as e:
        print(f"Помилка: {e}")

    # -- ТЕСТ 3: get_logs З фільтром по адресі (topics[2] = наша адреса) --
    print()
    print("=" * 60)
    print("ТЕСТ 3: get_logs З фільтром по адресі topics[2]")
    print("=" * 60)
    wallet_checksum = Web3.to_checksum_address(WALLET_ADDRESS)
    topic_addr = address_to_topic(wallet_checksum)
    print(f"  address_topic = {topic_addr}")
    try:
        logs = w3.eth.get_logs({
            "fromBlock": block_num,
            "toBlock": block_num,
            "address": Web3.to_checksum_address(USDT_CONTRACT),
            "topics": [TRANSFER_TOPIC, None, [topic_addr]],
        })
        print(f"Отримано {len(logs)} логів")
        for log in logs:
            topics = log.get("topics", [])
            data = to_hex(log.get("data", "0x0"))
            value = int(data, 16) if data and data != "0x" else 0
            tx_h = to_hex(log.get("transactionHash", ""))
            print(f"  TX: {tx_h[:20]}... amount={value/1e18:.2f} USDT")
        if len(logs) == 0:
            print("  НІЧОГО НЕ ЗНАЙДЕНО - фільтр по topics[2] не працює на QuickNode!")
    except Exception as e:
        print(f"Помилка: {e}")

    # -- ТЕСТ 4: get_logs з topics[2] без обгортки у список --
    print()
    print("=" * 60)
    print("ТЕСТ 4: get_logs topics[2] = topic_addr (без списку)")
    print("=" * 60)
    try:
        logs = w3.eth.get_logs({
            "fromBlock": block_num,
            "toBlock": block_num,
            "address": Web3.to_checksum_address(USDT_CONTRACT),
            "topics": [TRANSFER_TOPIC, None, topic_addr],
        })
        print(f"Отримано {len(logs)} логів")
        for log in logs:
            data = to_hex(log.get("data", "0x0"))
            value = int(data, 16) if data and data != "0x" else 0
            tx_h = to_hex(log.get("transactionHash", ""))
            print(f"  TX: {tx_h[:20]}... amount={value/1e18:.2f} USDT")
        if len(logs) == 0:
            print("  НІЧОГО НЕ ЗНАЙДЕНО")
    except Exception as e:
        print(f"Помилка: {e}")

    print()
    print("Готово.")


if __name__ == "__main__":
    main()
