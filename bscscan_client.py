"""
Модуль для роботи з BSC через QuickNode RPC.
Використовує get_logs з topics[2]=[address_topic] для фільтрації на рівні RPC.
Діапазонні запити замість поблокових — 20x економія API credits.
"""
import time
from web3 import Web3
from typing import List, Dict, Optional, Any
from config import (
    WALLET_ADDRESS, QUICKNODE_BSC_NODE, GETBLOCK_BSC_NODE,
    REQUEST_DELAY, USE_BLOCK_TIMESTAMP,
    INITIAL_CONNECTION_DELAY, USE_FALLBACK_ENDPOINT,
)

USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _to_hex(val: Any) -> str:
    if val is None:
        return ""
    if hasattr(val, "hex"):
        h = val.hex()
        return h if h.startswith("0x") else "0x" + h
    return str(val)


def _extract_address(topic: Any) -> str:
    h = _to_hex(topic).replace("0x", "").lower()
    if len(h) < 40:
        h = h.zfill(64)
    return "0x" + h[-40:]


class BSCscanClient:
    def __init__(self, rpc_url: str = None):
        self.rpc_url = (rpc_url or QUICKNODE_BSC_NODE).rstrip("/")
        if not self.rpc_url:
            raise ValueError("QUICKNODE_BSC_NODE не встановлено!")

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 30}))
        self.usdt_contract = Web3.to_checksum_address(USDT_CONTRACT_BSC)
        self.wallet_lower = WALLET_ADDRESS.lower()

        raw = WALLET_ADDRESS.replace("0x", "").lower()
        self.wallet_topic = "0x" + raw.zfill(64)

        if INITIAL_CONNECTION_DELAY > 0:
            print(f"⏳ Очікування {INITIAL_CONNECTION_DELAY} сек...")
            time.sleep(INITIAL_CONNECTION_DELAY)

        self._verify_connection()

        print(f"🔧 USDT контракт: {self.usdt_contract}")
        print(f"🔧 Wallet: {self.wallet_lower}")
        print(f"🔧 Wallet topic: {self.wallet_topic}")

    def _verify_connection(self):
        print(f"🔌 Підключення: {self.rpc_url[:50]}...")
        try:
            n = self.w3.eth.block_number
            print(f"✅ QuickNode OK. Блок: {n}")
            return
        except Exception as e:
            print(f"⚠️ QuickNode: {e}")

        if USE_FALLBACK_ENDPOINT and GETBLOCK_BSC_NODE:
            print("⚠️ Спробуємо GetBlock...")
            try:
                self.rpc_url = GETBLOCK_BSC_NODE.rstrip("/")
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 30}))
                n = self.w3.eth.block_number
                print(f"✅ GetBlock OK. Блок: {n}")
                return
            except Exception as e2:
                print(f"❌ GetBlock: {e2}")
        raise ConnectionError("Не вдалося підключитися до RPC")

    def get_latest_block(self) -> Optional[int]:
        try:
            return self.w3.eth.block_number
        except Exception as e:
            print(f"❌ get_latest_block: {e}")
            return None

    def run_diagnostic(self) -> bool:
        """
        Діагностика при старті: шукаємо останню USDT транзакцію НА гаманець.
        Якщо знаходимо — все працює. Якщо ні — є проблема з фільтрацією.
        """
        print(f"\n{'='*60}")
        print(f"🧪 ДІАГНОСТИКА")
        print(f"{'='*60}")

        latest = self.get_latest_block()
        if not latest:
            print("❌ Не вдалося отримати блок")
            return False

        print(f"📦 Останній блок: {latest}")

        # Крок 1: Шукаємо USDT транзакції НА наш гаманець за останні ~50 хвилин (10000 блоків)
        from_block = max(0, latest - 10000)
        print(f"🔍 Пошук USDT на {self.wallet_lower[:12]}... в блоках {from_block}-{latest}...")

        try:
            logs = self.w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": latest,
                "address": self.usdt_contract,
                "topics": [TRANSFER_EVENT_TOPIC, None, [self.wallet_topic]],
            })

            if logs:
                print(f"✅ Знайдено {len(logs)} USDT транзакцій за ~50 хв!")
                for lg in logs:
                    tx_hash = _to_hex(lg.get("transactionHash", ""))
                    bn = lg.get("blockNumber", 0)
                    data_hex = _to_hex(lg.get("data", "0x0"))
                    value = int(data_hex, 16) if data_hex and data_hex != "0x" else 0
                    amount = value / 1e18
                    from_addr = _extract_address(lg["topics"][1]) if len(lg.get("topics", [])) > 1 else "?"
                    print(f"   💰 Блок {bn}: {amount:.2f} USDT від {from_addr[:16]}...")
                    print(f"      TX: {tx_hash}")
                print(f"✅ get_logs з topics[2] фільтром ПРАЦЮЄ!")
                return True
            else:
                print(f"ℹ️ 0 транзакцій за 10000 блоків — можливо давно не було платежів")
        except Exception as e:
            print(f"⚠️ Помилка get_logs (10000 блоків): {e}")
            print(f"   Спробуємо менший діапазон...")

            # Спробуємо менший діапазон
            from_block = max(0, latest - 1000)
            try:
                logs = self.w3.eth.get_logs({
                    "fromBlock": from_block,
                    "toBlock": latest,
                    "address": self.usdt_contract,
                    "topics": [TRANSFER_EVENT_TOPIC, None, [self.wallet_topic]],
                })
                print(f"   1000 блоків: знайдено {len(logs)} логів")
                if logs:
                    print(f"   ✅ Фільтрація працює!")
                    return True
            except Exception as e2:
                print(f"   ⚠️ 1000 блоків теж помилка: {e2}")

        # Крок 2: Перевірка без фільтра (є взагалі USDT події?)
        print(f"\n🔍 Контрольний тест: ALL USDT в 1 блоці (без wallet фільтра)...")
        try:
            logs_all = self.w3.eth.get_logs({
                "fromBlock": latest,
                "toBlock": latest,
                "address": self.usdt_contract,
                "topics": [TRANSFER_EVENT_TOPIC],
            })
            print(f"   Блок {latest}: {len(logs_all)} USDT подій (всіх)")
            if logs_all:
                print(f"   ✅ RPC повертає логи — get_logs працює")
            else:
                print(f"   ⚠️ 0 подій навіть без фільтра — дивно")
        except Exception as e:
            print(f"   ❌ Помилка: {e}")
            return False

        print(f"{'='*60}")
        return True

    def get_token_transactions(
        self, start_block: int = 0, end_block: int = 99999999
    ) -> List[Dict]:
        """
        Пошук USDT транзакцій НА адресу.
        ОДИН діапазонний запит get_logs з topics[2]=[wallet_topic].
        Якщо діапазон завеликий (413), розбиває на менші частини.
        """
        start_block = max(0, start_block)
        if start_block > end_block:
            return []

        block_count = end_block - start_block + 1
        print(f"🔍 get_logs {start_block}-{end_block} ({block_count} блоків)")

        filter_params = {
            "fromBlock": start_block,
            "toBlock": end_block,
            "address": self.usdt_contract,
            "topics": [TRANSFER_EVENT_TOPIC, None, [self.wallet_topic]],
        }

        all_txs = []

        try:
            logs = self.w3.eth.get_logs(filter_params)
            print(f"   📋 Отримано {len(logs)} подій")

            for lg in logs:
                bn = lg.get("blockNumber", 0)
                tx = self._parse_log(lg, bn)
                if tx:
                    all_txs.append(tx)
                    print(f"   ✅ Блок {bn}: {int(tx['value'])/1e18:.2f} USDT від {tx['from'][:16]}...")

        except Exception as e:
            err_str = str(e).lower()
            print(f"   ⚠️ get_logs ПОМИЛКА: {e}")

            if "413" in err_str or "too large" in err_str or "query returned more" in err_str:
                print(f"   🔄 Діапазон завеликий, по 1 блоку...")
                all_txs = self._get_logs_per_block(start_block, end_block)

        print(f"   ✅ Результат: {len(all_txs)} транзакцій USDT")
        return all_txs

    def _get_logs_per_block(self, start_block: int, end_block: int) -> List[Dict]:
        """Запасний варіант: поблочні запити."""
        txs = []
        for bn in range(start_block, end_block + 1):
            try:
                logs = self.w3.eth.get_logs({
                    "fromBlock": bn,
                    "toBlock": bn,
                    "address": self.usdt_contract,
                    "topics": [TRANSFER_EVENT_TOPIC, None, [self.wallet_topic]],
                })
                for lg in logs:
                    tx = self._parse_log(lg, bn)
                    if tx:
                        txs.append(tx)
                        print(f"      ✅ Блок {bn}: {int(tx['value'])/1e18:.2f} USDT")
            except Exception as e:
                print(f"      ⚠️ Блок {bn}: {e}")

            if bn < end_block and REQUEST_DELAY > 0:
                time.sleep(REQUEST_DELAY)
        return txs

    def _parse_log(self, lg: Any, block_num: int) -> Optional[Dict]:
        try:
            topics = lg.get("topics", [])
            if len(topics) < 3:
                return None

            from_addr = _extract_address(topics[1])
            to_addr = _extract_address(topics[2])

            data = lg.get("data", "0x0")
            data_hex = _to_hex(data)
            value = int(data_hex, 16) if data_hex and data_hex != "0x" else 0

            tx_hash = _to_hex(lg.get("transactionHash", ""))
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash

            timestamp = 0
            if USE_BLOCK_TIMESTAMP:
                try:
                    b = self.w3.eth.get_block(block_num)
                    timestamp = b.get("timestamp", 0) if b else 0
                except Exception:
                    pass

            return {
                "hash": tx_hash,
                "from": from_addr,
                "to": to_addr,
                "value": str(value),
                "tokenSymbol": "USDT",
                "tokenDecimal": "18",
                "timeStamp": str(timestamp),
                "blockNumber": str(block_num),
                "contractAddress": self.usdt_contract,
            }
        except Exception as e:
            print(f"   ⚠️ _parse_log: {e}")
            return None

    def format_transaction(self, tx: Dict) -> Dict:
        value = int(tx.get("value", 0))
        decimals = int(tx.get("tokenDecimal", 18))
        amount = value / (10 ** decimals)
        ts = int(tx.get("timeStamp", 0))
        from datetime import datetime
        time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"
        return {
            "hash": tx.get("hash", ""),
            "amount": amount,
            "symbol": tx.get("tokenSymbol", "USDT"),
            "from_address": tx.get("from", ""),
            "to_address": tx.get("to", ""),
            "timestamp": time_str,
            "is_incoming": True,
            "contract_address": tx.get("contractAddress", ""),
            "block_number": tx.get("blockNumber", ""),
        }
