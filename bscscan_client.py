"""
Модуль для моніторингу USDT транзакцій на BSC.

Стратегія:
1. Спробувати BSCScan API (api.bscscan.com) — може ще працювати
2. Якщо ні — QuickNode RPC: get_logs з topics[0] only + фільтрація в Python
   (topics[2] фільтр НЕ працює на QuickNode BSC free tier)
"""
import time
import requests as http_requests
from web3 import Web3
from typing import List, Dict, Optional, Any
from config import (
    WALLET_ADDRESS, QUICKNODE_BSC_NODE, GETBLOCK_BSC_NODE,
    INITIAL_CONNECTION_DELAY, USE_FALLBACK_ENDPOINT, BSCSCAN_API_KEY,
    CHECK_INTERVAL,
)

USDT_CONTRACT_BSC = "0x55d398326f99059fF775485246999027B3197955"
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BSCSCAN_API_URL = "https://api.bscscan.com/api"


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
        self.usdt_lower = USDT_CONTRACT_BSC.lower()
        self.wallet_lower = WALLET_ADDRESS.lower()

        self.use_bscscan_api = False

        if INITIAL_CONNECTION_DELAY > 0:
            print(f"⏳ Очікування {INITIAL_CONNECTION_DELAY} сек...")
            time.sleep(INITIAL_CONNECTION_DELAY)

        self._verify_connection()

    def _verify_connection(self):
        print(f"🔌 Підключення: {self.rpc_url[:50]}...")
        try:
            n = self.w3.eth.block_number
            print(f"✅ RPC OK. Блок: {n}")
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

    # =====================================================
    #  ДІАГНОСТИКА
    # =====================================================

    def run_diagnostic(self) -> bool:
        print(f"\n{'='*60}")
        print(f"🧪 ДІАГНОСТИКА")
        print(f"{'='*60}")

        latest = self.get_latest_block()
        if not latest:
            print("❌ Не вдалося отримати блок")
            return False

        print(f"📦 Останній блок: {latest}")

        # Тест 1: BSCScan API
        print(f"\n--- Тест BSCScan API ---")
        bscscan_ok = self._test_bscscan_api(latest)

        if bscscan_ok:
            self.use_bscscan_api = True
            print(f"✅ Метод: BSCScan API")
        else:
            self.use_bscscan_api = False
            print(f"⚠️ BSCScan API недоступний, використовуємо RPC")

            # Тест 2: RPC (get_logs без topics[2])
            print(f"\n--- Тест RPC (get_logs) ---")
            self._test_rpc(latest)

        print(f"\n{'='*60}")
        return True

    def _test_bscscan_api(self, latest_block: int) -> bool:
        from_block = max(0, latest_block - 10000)
        print(f"🔍 BSCScan API: блоки {from_block}-{latest_block}...")

        try:
            txs = self._bscscan_get_transfers(from_block, latest_block)
            if txs is None:
                print(f"   ❌ BSCScan API не відповідає")
                return False

            print(f"   📋 Знайдено {len(txs)} вхідних USDT")
            for tx in txs[-3:]:
                amount = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                print(f"   💰 Блок {tx.get('blockNumber')}: {amount:.2f} USDT від {tx.get('from', '')[:16]}...")
            return True
        except Exception as e:
            print(f"   ❌ {e}")
            return False

    def _test_rpc(self, latest_block: int):
        print(f"🔍 RPC get_logs для блоку {latest_block} (всі USDT події)...")
        try:
            logs = self.w3.eth.get_logs({
                "fromBlock": latest_block,
                "toBlock": latest_block,
                "address": self.usdt_contract,
                "topics": [TRANSFER_EVENT_TOPIC],
            })
            print(f"   📋 Блок {latest_block}: {len(logs)} USDT подій")

            our_txs = 0
            for lg in logs:
                topics = lg.get("topics", [])
                if len(topics) >= 3:
                    to_addr = _extract_address(topics[2])
                    if to_addr == self.wallet_lower:
                        our_txs += 1
                        data_hex = _to_hex(lg.get("data", "0x0"))
                        value = int(data_hex, 16) if data_hex and data_hex != "0x" else 0
                        print(f"   💰 НАШ ПЛАТІЖ! {value/1e18:.2f} USDT")

            if our_txs == 0:
                print(f"   ℹ️ Немає наших транзакцій у цьому блоці (нормально)")
            print(f"   ✅ RPC працює!")
        except Exception as e:
            print(f"   ⚠️ RPC помилка: {e}")

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

        if self.use_bscscan_api:
            print(f"🔍 BSCScan API: блоки {start_block}-{end_block} ({block_count})")
            txs = self._bscscan_get_transfers(start_block, end_block)
            if txs is not None:
                self._log_found(txs)
                return txs
            print(f"   ⚠️ BSCScan не відповів, переключаюсь на RPC...")

        print(f"🔍 RPC: блоки {start_block}-{end_block} ({block_count})")
        txs = self._rpc_get_transfers(start_block, end_block)
        self._log_found(txs)
        return txs

    def _log_found(self, txs: List[Dict]):
        if txs:
            for tx in txs:
                amount = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                print(f"   💰 Блок {tx.get('blockNumber')}: {amount:.2f} USDT від {tx.get('from', '')[:16]}...")
        print(f"   ✅ Знайдено {len(txs)} вхідних USDT транзакцій")

    # =====================================================
    #  МЕТОД 1: BSCScan API
    # =====================================================

    def _bscscan_get_transfers(
        self, start_block: int, end_block: int
    ) -> Optional[List[Dict]]:
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": USDT_CONTRACT_BSC,
            "address": WALLET_ADDRESS,
            "startblock": start_block,
            "endblock": end_block,
            "page": 1,
            "offset": 100,
            "sort": "asc",
        }
        if BSCSCAN_API_KEY:
            params["apikey"] = BSCSCAN_API_KEY

        try:
            resp = http_requests.get(BSCSCAN_API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status", "0")
            message = data.get("message", "")
            result = data.get("result", [])

            if status == "1" and isinstance(result, list):
                return [
                    tx for tx in result
                    if tx.get("to", "").lower() == self.wallet_lower
                ]

            if message == "No transactions found" or result == []:
                return []

            if isinstance(result, str):
                if "rate limit" in result.lower():
                    print(f"   ⚠️ BSCScan rate limit")
                    return None
                if "api" in result.lower() and ("v2" in result.lower() or "deprecated" in result.lower()):
                    print(f"   ❌ BSCScan API закритий: {result}")
                    self.use_bscscan_api = False
                    return None

            print(f"   ⚠️ BSCScan: status={status}, msg={message}")
            return None

        except http_requests.exceptions.ConnectionError:
            print(f"   ❌ BSCScan: з'єднання не вдалося")
            return None
        except Exception as e:
            print(f"   ❌ BSCScan: {e}")
            return None

    # =====================================================
    #  МЕТОД 2: RPC (QuickNode) — без topics[2], фільтрація в Python
    # =====================================================

    def _rpc_get_transfers(
        self, start_block: int, end_block: int
    ) -> List[Dict]:
        """
        Отримує ВСІ USDT Transfer логи і фільтрує для нашого гаманця в Python.
        topics[2] фільтрація не працює на QuickNode BSC free tier.
        Скануємо по 1 блоку щоб уникнути 413.
        """
        all_txs = []
        blocks_scanned = 0

        for bn in range(start_block, end_block + 1):
            try:
                logs = self.w3.eth.get_logs({
                    "fromBlock": bn,
                    "toBlock": bn,
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

                    tx = self._parse_log_rpc(lg, bn)
                    if tx:
                        all_txs.append(tx)

            except Exception as e:
                err_str = str(e).lower()
                if "413" in err_str or "too large" in err_str:
                    print(f"      ⚠️ Блок {bn}: 413 (забагато даних)")
                else:
                    print(f"      ⚠️ Блок {bn}: {e}")

            blocks_scanned += 1

            if bn < end_block:
                time.sleep(0.5)

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

            return {
                "hash": tx_hash,
                "from": from_addr,
                "to": to_addr,
                "value": str(value),
                "tokenSymbol": "USDT",
                "tokenDecimal": "18",
                "timeStamp": "0",
                "blockNumber": str(block_num),
                "contractAddress": USDT_CONTRACT_BSC,
            }
        except Exception as e:
            print(f"   ⚠️ _parse_log: {e}")
            return None

    # =====================================================
    #  ФОРМАТУВАННЯ
    # =====================================================

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
