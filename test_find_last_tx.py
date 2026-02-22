"""
ТЕСТ: Сканує блоки назад від останнього, знаходить ОСТАННЮ USDT транзакцію
на гаманець і надсилає в Telegram. Логує все.

Запуск: python test_find_last_tx.py
"""
import sys
import time
import traceback
import requests
from web3 import Web3
from config import QUICKNODE_BSC_NODE, WALLET_ADDRESS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

MAX_SCAN_BLOCKS = 3000  # максимум блоків для пошуку (~15 хв BSC)


def log(msg):
    print(f"[LOG] {msg}")


def log_err(msg):
    print(f"[ERROR] {msg}")


def to_hex(val):
    if val is None:
        return ""
    if hasattr(val, "hex"):
        h = val.hex()
        return h if h.startswith("0x") else "0x" + h
    return str(val)


def extract_addr(topic):
    h = to_hex(topic).replace("0x", "").lower()
    if len(h) < 40:
        h = h.zfill(64)
    return "0x" + h[-40:]


def address_to_topic(addr):
    raw = addr.replace("0x", "").lower()
    return "0x" + raw.zfill(64)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    log(f"Telegram: відправка в {TELEGRAM_CHANNEL_ID}...")
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        log(f"Telegram: status={resp.status_code}, ok={data.get('ok')}")
        if not data.get("ok"):
            log_err(f"Telegram error: {data.get('description', 'unknown')}")
        return data.get("ok", False)
    except Exception as e:
        log_err(f"Telegram: {e}")
        traceback.print_exc()
        return False


def main():
    wallet = WALLET_ADDRESS.lower()
    usdt_checksum = Web3.to_checksum_address(USDT_CONTRACT)
    topic_addr = address_to_topic(WALLET_ADDRESS)

    log(f"Гаманець: {WALLET_ADDRESS}")
    log(f"USDT: {USDT_CONTRACT}")
    log(f"Topic адреси: {topic_addr}")
    print()

    # === КРОК 1: Підключення ===
    print("=" * 60)
    log("КРОК 1: Підключення")
    print("=" * 60)
    try:
        w3 = Web3(Web3.HTTPProvider(QUICKNODE_BSC_NODE.rstrip("/"), request_kwargs={"timeout": 30}))
        latest = w3.eth.block_number
        log(f"OK. Блок: {latest}")
    except Exception as e:
        log_err(f"Підключення: {e}")
        traceback.print_exc()
        return
    print()

    # === КРОК 2: Тестуємо який метод get_logs працює (1 блок) ===
    print("=" * 60)
    log("КРОК 2: Тест методів get_logs на 1 блоці")
    print("=" * 60)
    test_block = latest - 1

    # Метод A: з фільтром topics[2]=[addr]
    method_a = False
    try:
        logs_a = w3.eth.get_logs({
            "fromBlock": test_block, "toBlock": test_block,
            "address": usdt_checksum,
            "topics": [TRANSFER_TOPIC, None, [topic_addr]],
        })
        log(f"Метод A (topics[2]=[addr]): {len(logs_a)} логів - OK")
        method_a = True
    except Exception as e:
        log_err(f"Метод A: {e}")

    # Метод B: без фільтра (всі USDT)
    method_b = False
    method_b_count = 0
    try:
        logs_b = w3.eth.get_logs({
            "fromBlock": test_block, "toBlock": test_block,
            "address": usdt_checksum,
            "topics": [TRANSFER_TOPIC, None, None],
        })
        method_b_count = len(logs_b)
        log(f"Метод B (без фільтра): {method_b_count} логів - OK")
        method_b = True
    except Exception as e:
        log_err(f"Метод B: {e}")

    if not method_a and not method_b:
        log_err("Жоден метод get_logs не працює! Спробуємо пошук по receipt...")

    use_filter = method_a
    log(f"Буду використовувати: {'Метод A (з фільтром)' if use_filter else 'Метод B (без фільтра)'}")
    print()

    # === КРОК 3: Сканування блоків назад для пошуку останньої TX ===
    print("=" * 60)
    log(f"КРОК 3: Сканування блоків {latest} -> {latest - MAX_SCAN_BLOCKS}")
    print("=" * 60)

    found_tx = None
    blocks_scanned = 0
    blocks_with_error = 0

    scan_start = latest
    scan_end = max(latest - MAX_SCAN_BLOCKS, 0)

    # Скануємо чанками по 5 блоків для швидкості (якщо фільтр працює)
    chunk = 5 if use_filter else 1
    bn = scan_start

    while bn > scan_end and found_tx is None:
        from_block = max(bn - chunk + 1, scan_end)
        to_block = bn

        try:
            if use_filter:
                logs = w3.eth.get_logs({
                    "fromBlock": from_block, "toBlock": to_block,
                    "address": usdt_checksum,
                    "topics": [TRANSFER_TOPIC, None, [topic_addr]],
                })
            else:
                logs = w3.eth.get_logs({
                    "fromBlock": from_block, "toBlock": to_block,
                    "address": usdt_checksum,
                    "topics": [TRANSFER_TOPIC, None, None],
                })

            blocks_scanned += (to_block - from_block + 1)

            # Шукаємо наші TX
            our_logs = []
            for lg in logs:
                topics = lg.get("topics", [])
                if len(topics) < 3:
                    continue
                to_addr = extract_addr(topics[2])
                if to_addr.lower() == wallet:
                    our_logs.append(lg)

            if our_logs:
                # Беремо останній (найновіший) лог
                lg = our_logs[-1]
                topics = lg.get("topics", [])
                from_addr = extract_addr(topics[1])
                to_addr = extract_addr(topics[2])
                data_hex = to_hex(lg.get("data", "0x0"))
                value = int(data_hex, 16) if data_hex and data_hex != "0x" else 0
                amount = value / 1e18
                tx_hash = to_hex(lg.get("transactionHash", ""))
                if not tx_hash.startswith("0x"):
                    tx_hash = "0x" + tx_hash
                block_num = lg.get("blockNumber", 0)
                if hasattr(block_num, "hex"):
                    block_num = int(block_num.hex(), 16)
                block_num = int(block_num)

                # Час
                time_str = "N/A"
                try:
                    block_data = w3.eth.get_block(block_num)
                    ts = block_data.get("timestamp", 0)
                    if ts:
                        from datetime import datetime
                        time_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception as te:
                    log(f"  Timestamp: {te}")

                found_tx = {
                    "hash": tx_hash,
                    "from": from_addr,
                    "to": to_addr,
                    "amount": amount,
                    "block": block_num,
                    "timestamp": time_str,
                }
                log(f"  ✅ ЗНАЙДЕНО! Блок {block_num}, {amount:.2f} USDT, hash={tx_hash[:20]}...")
                break

        except Exception as e:
            blocks_with_error += 1
            err = str(e).lower()
            if "413" in err or "too large" in err:
                # Зменшуємо чанк
                if chunk > 1:
                    chunk = 1
                    log(f"  Блок {to_block}: 413, зменшую чанк до 1")
                    continue
            elif blocks_with_error <= 3:
                log_err(f"  Блок {from_block}-{to_block}: {e}")

        bn = from_block - 1

        # Прогрес кожні 100 блоків
        if blocks_scanned % 100 == 0 and blocks_scanned > 0:
            log(f"  Просканував {blocks_scanned} блоків...")

        time.sleep(0.3)

    log(f"Просканував {blocks_scanned} блоків, помилок: {blocks_with_error}")
    print()

    if not found_tx:
        log_err(f"TX не знайдено в останніх {MAX_SCAN_BLOCKS} блоках!")
        return

    # === КРОК 4: Надсилання в Telegram ===
    print("=" * 60)
    log("КРОК 4: Надсилання в Telegram")
    print("=" * 60)

    tx_link = f"https://bscscan.com/tx/{found_tx['hash']}"
    message = f"""🧪 <b>ТЕСТ - Остання USDT транзакція:</b>

📊 <b>Сума:</b> {found_tx['amount']:.2f} USDT
📤 <b>Від:</b> <code>{found_tx['from']}</code>
📥 <b>До:</b> <code>{found_tx['to']}</code>
📦 <b>Блок:</b> {found_tx['block']}
🕐 <b>Час:</b> {found_tx['timestamp']}

🔗 <a href="{tx_link}">Переглянути на BSCScan</a>

<i>Метод: {'get_logs з фільтром' if use_filter else 'get_logs без фільтра'}
Просканував: {blocks_scanned} блоків</i>"""

    log(f"TX: {found_tx['hash']}")
    log(f"Сума: {found_tx['amount']:.2f} USDT")
    log(f"Блок: {found_tx['block']}")

    ok = send_telegram(message)
    if ok:
        log("✅ Надіслано в Telegram!")
    else:
        log_err("❌ Telegram не вдалося!")
    print()

    print("=" * 60)
    log("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    main()
