"""
Модуль для роботи з BSC через QuickNode RPC.
Використовує get_logs з topics[2]=[address_topic] — підтверджено працює на QuickNode.
Запити по 1 блоку щоб уникнути 413.
"""
import time
from web3 import Web3
from typing import List, Dict, Optional, Any
from config import (
    WALLET_ADDRESS, QUICKNODE_BSC_NODE, GETBLOCK_BSC_NODE,
    REQUEST_DELAY, MAX_BLOCKS_PER_CHECK, USE_BLOCK_TIMESTAMP,
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

        # Адреса гаманця як topic (32 байти, padded зліва нулями)
        raw = WALLET_ADDRESS.replace("0x", "").lower()
        self.wallet_topic = "0x" + raw.zfill(64)

        if INITIAL_CONNECTION_DELAY > 0:
            print(f"⏳ Очікування {INITIAL_CONNECTION_DELAY} сек...")
            time.sleep(INITIAL_CONNECTION_DELAY)

        self._verify_connection()

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

    def get_token_transactions(
        self, address: str = WALLET_ADDRESS, start_block: int = 0, end_block: int = 99999999
    ) -> List[Dict]:
        """
        Пошук USDT транзакцій НА адресу.
        Використовує topics[2]=[wallet_topic] — QuickNode фільтрує на рівні RPC.
        Запити по 1 блоку щоб уникнути 413.
        """
        latest = self.get_latest_block()
        if not latest:
            return []

        end_block = min(end_block, latest)
        start_block = max(0, start_block)
        if start_block > end_block:
            return []

        if (end_block - start_block + 1) > MAX_BLOCKS_PER_CHECK:
            start_block = end_block - (MAX_BLOCKS_PER_CHECK - 1)

        block_count = end_block - start_block + 1
        print(f"🔍 Пошук USDT в блоках {start_block}-{end_block} ({block_count} блоків)")

        all_txs = []

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
                        all_txs.append(tx)
                        print(f"   ✅ Блок {bn}: {int(tx['value'])/1e18:.2f} USDT від {tx['from'][:12]}...")

            except Exception as e:
                err = str(e).lower()
                if "413" not in err and "too large" not in err:
                    print(f"   ⚠️ Блок {bn}: {e}")

            if bn < end_block and REQUEST_DELAY > 0:
                time.sleep(REQUEST_DELAY)

        print(f"✅ Знайдено {len(all_txs)} транзакцій USDT")
        return all_txs

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
