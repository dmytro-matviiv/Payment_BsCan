"""
Модуль для моніторингу USDT транзакцій на BSC.

Стратегія:
- QuickNode RPC: get_logs з topics[0] + фільтрація в Python
- Опційний fallback на GetBlock RPC, якщо QuickNode недоступний
"""
import time
from web3 import Web3
from typing import List, Dict, Optional, Any
from config import (
    WALLET_ADDRESS, QUICKNODE_BSC_NODE, GETBLOCK_BSC_NODE,
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

        self.use_etherscan = False

        if INITIAL_CONNECTION_DELAY > 0:
            print(f"⏳ Очікування {INITIAL_CONNECTION_DELAY} сек...", flush=True)
            time.sleep(INITIAL_CONNECTION_DELAY)

        self._verify_connection()

    def _verify_connection(self):
        print(f"🔌 Підключення: {self.rpc_url[:50]}...", flush=True)
        try:
            n = self.w3.eth.block_number
            print(f"✅ RPC OK. Блок: {n}", flush=True)
            return
        except Exception as e:
            print(f"⚠️ QuickNode: {e}", flush=True)

        if USE_FALLBACK_ENDPOINT and GETBLOCK_BSC_NODE:
            print("⚠️ Спробуємо GetBlock...", flush=True)
            try:
                self.rpc_url = GETBLOCK_BSC_NODE.rstrip("/")
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 30}))
                n = self.w3.eth.block_number
                print(f"✅ GetBlock OK. Блок: {n}", flush=True)
                return
            except Exception as e2:
                print(f"❌ GetBlock: {e2}", flush=True)
        raise ConnectionError("Не вдалося підключитися до RPC")

    def get_latest_block(self) -> Optional[int]:
        try:
            return self.w3.eth.block_number
        except Exception as e:
            print(f"❌ get_latest_block: {e}", flush=True)
            return None

    # =====================================================
    #  ДІАГНОСТИКА
    # =====================================================

    def run_diagnostic(self) -> bool:
        print(f"\n{'='*60}", flush=True)
        print(f"🧪 ДІАГНОСТИКА", flush=True)
        print(f"{'='*60}", flush=True)

        latest = self.get_latest_block()
        if not latest:
            print("❌ Не вдалося отримати блок", flush=True)
            return False

        print(f"📦 Останній блок: {latest}", flush=True)

        self.use_etherscan = False
        print(f"\n--- Тест RPC (get_logs) ---", flush=True)
        self._test_rpc(latest)
        print(f"🌐 Метод: QuickNode RPC", flush=True)

        print(f"{'='*60}", flush=True)
        return True

    def _test_rpc(self, latest_block: int):
        print(f"🔍 RPC get_logs для блоку {latest_block} (всі USDT події)...", flush=True)
        try:
            logs = self.w3.eth.get_logs({
                "fromBlock": latest_block,
                "toBlock": latest_block,
                "address": self.usdt_contract,
                "topics": [TRANSFER_EVENT_TOPIC],
            })
            print(f"   📋 Блок {latest_block}: {len(logs)} USDT подій", flush=True)

            our_count = 0
            for lg in logs:
                topics = lg.get("topics", [])
                if len(topics) >= 3:
                    to_addr = _extract_address(topics[2])
                    if to_addr == self.wallet_lower:
                        our_count += 1
                        data_hex = _to_hex(lg.get("data", "0x0"))
                        value = int(data_hex, 16) if data_hex and data_hex != "0x" else 0
                        print(f"   💰 НАШ ПЛАТІЖ! {value/1e18:.2f} USDT", flush=True)

            if our_count == 0:
                print(f"   ℹ️ Немає наших транзакцій у цьому блоці (нормально)", flush=True)
            print(f"   ✅ RPC працює!", flush=True)
        except Exception as e:
            print(f"   ⚠️ RPC помилка: {e}", flush=True)

    # =====================================================
    #  ПОШУК ТРАНЗАКЦІЙ
    # =====================================================

    def get_token_transactions(
        self, start_block: int = 0, end_block: int = 99999999
    ) -> List[Dict]:
        start_block = max(0, start_block)
        if start_block > end_block:
            return []

        block_count = end_block - start_block + 1

        print(f"🔍 RPC: блоки {start_block}-{end_block} ({block_count})", flush=True)
        txs = self._rpc_get_transfers(start_block, end_block)
        self._log_found(txs)
        return txs

    def _log_found(self, txs: List[Dict]):
        if txs:
            for tx in txs:
                amount = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                print(f"   💰 Блок {tx.get('blockNumber')}: {amount:.2f} USDT від {tx.get('from', '')[:16]}...", flush=True)
        print(f"   ✅ Знайдено {len(txs)} вхідних USDT транзакцій", flush=True)

    # =====================================================
    #  МЕТОД: RPC — без topics[2], фільтрація в Python
    # =====================================================

    def _rpc_get_transfers(
        self, start_block: int, end_block: int
    ) -> List[Dict]:
        """
        Отримує ВСІ USDT Transfer логи і фільтрує для нашого гаманця в Python.
        Спочатку пробує чанки по 5 блоків (5x менше API calls).
        Якщо 413 — зменшує розмір чанку.
        """
        all_txs = []
        chunk_size = 20
        pos = start_block

        while pos <= end_block:
            chunk_end = min(pos + chunk_size - 1, end_block)

            try:
                logs = self.w3.eth.get_logs({
                    "fromBlock": pos,
                    "toBlock": chunk_end,
                    "address": self.usdt_contract,
                    "topics": [TRANSFER_EVENT_TOPIC],
                })

                for lg in logs:
                    topics = lg.get("topics", [])
                    if len(topics) < 3:
                        continue

                    to_addr = _extract_address(topics[2])
                    if to_addr != self.wallet_lower:
                        continue

                    bn = lg.get("blockNumber", pos)
                    tx = self._parse_log_rpc(lg, bn)
                    if tx:
                        all_txs.append(tx)
                        amount = int(tx["value"]) / 1e18
                        print(f"      🎯 Блок {bn}: {amount:.2f} USDT", flush=True)

                pos = chunk_end + 1

            except Exception as e:
                err_str = str(e).lower()
                if ("413" in err_str or "too large" in err_str) and chunk_size > 1:
                    chunk_size = max(1, chunk_size // 2)
                    print(f"      ⚠️ 413 — чанк → {chunk_size}", flush=True)
                    continue

                print(f"      ⚠️ {pos}-{chunk_end}: {e}", flush=True)
                pos = chunk_end + 1

            if pos <= end_block:
                time.sleep(0.3)

        return all_txs

    def _parse_log_rpc(self, lg: Any, block_num: int) -> Optional[Dict]:
        try:
            topics = lg.get("topics", [])
            from_addr = _extract_address(topics[1])
            to_addr = _extract_address(topics[2])

            data_hex = _to_hex(lg.get("data", "0x0"))
            value = int(data_hex, 16) if data_hex and data_hex != "0x" else 0

            tx_hash = _to_hex(lg.get("transactionHash", ""))
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash

            timestamp = 0
            try:
                block = self.w3.eth.get_block(block_num)
                timestamp = block.get("timestamp", 0) if block else 0
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
                "contractAddress": USDT_CONTRACT_BSC,
            }
        except Exception as e:
            print(f"   ⚠️ _parse_log: {e}", flush=True)
            return None

    # =====================================================
    #  ФОРМАТУВАННЯ
    # =====================================================

    def format_transaction(self, tx: Dict) -> Dict:
        value = int(tx.get("value", 0))
        decimals = int(tx.get("tokenDecimal", 18))
        amount = value / (10 ** decimals)

        ts = int(tx.get("timeStamp", 0))
        time_str = "N/A"
        if ts:
            from datetime import datetime, timezone, timedelta
            kyiv_tz = timezone(timedelta(hours=2))
            time_str = datetime.fromtimestamp(ts, tz=kyiv_tz).strftime("%Y-%m-%d %H:%M:%S (Київ)")

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
