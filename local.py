# -*- coding: utf-8 -*-
import asyncio
import ssl
import json
import time
import uuid
from loguru import logger
import websockets
from concurrent.futures import ThreadPoolExecutor

async def connect_to_wss(user_id, proxy, user_agent, sleep_time):
    device_id = str(uuid.uuid4())
    logger.info(f"Using proxy: {proxy} with User-Agent: {user_agent}")
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    uri = "wss://proxy.wynd.network:4444/"

    while True:
        try:
            custom_headers = {
                "User-Agent": user_agent
            }

            async with websockets.connect(uri, ssl=ssl_context, extra_headers={
                "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi",
                "User-Agent": custom_headers["User-Agent"],
                "Proxy-Connection": "keep-alive"
            }, ping_interval=None) as websocket:

                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        logger.debug(send_message)
                        await websocket.send(send_message)
                        await asyncio.sleep(sleep_time)  # Thời gian ngủ tuỳ biến

                send_ping_task = asyncio.create_task(send_ping())
                try:
                    while True:
                        response = await websocket.recv()
                        message = json.loads(response)
                        logger.info(message)
                        if message.get("action") == "AUTH":
                            auth_response = {
                                "id": message["id"],
                                "origin_action": "AUTH",
                                "result": {
                                    "browser_id": device_id,
                                    "user_id": user_id,
                                    "user_agent": custom_headers['User-Agent'],
                                    "timestamp": int(time.time()),
                                    "device_type": "extension",
                                    "version": "4.20.2",
                                    "extension_id": "lkbnfiajjmbhnfledhphioinpickokdi"
                                }
                            }
                            logger.debug(auth_response)
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            logger.debug(pong_response)
                            await websocket.send(json.dumps(pong_response))
                finally:
                    send_ping_task.cancel()

        except Exception as e:
            logger.error(f"Error with proxy {proxy} and User-Agent {user_agent}: {str(e)}")
            break

async def start_worker(user_id, proxies, user_agents, worker_id, total_workers, sleep_time):
    proxy_count = len(proxies)
    user_agent_count = len(user_agents)

    while True:
        # Tính toán vị trí bắt đầu cho worker này để tránh trùng lặp với các worker khác
        index = (worker_id * proxy_count // total_workers) % proxy_count
        proxy = proxies[index]
        user_agent = user_agents[index % user_agent_count]
        
        await connect_to_wss(user_id, proxy, user_agent, sleep_time)
        await asyncio.sleep(1)  # Thời gian nghỉ giữa các lần gọi để luồng trả về kết quả liên tiếp

async def main():
    user_id = '2nQdty74gXxPPMTqEqoLFzaOJOi'  # Thay bằng User ID của bạn

    # Đọc proxy từ tệp proxy.txt
    with open('proxy.txt', 'r') as f:
        proxies = [line.strip() for line in f.readlines() if line.strip()]

    # Đọc user agent từ tệp user.txt
    with open('user.txt', 'r') as f:
        user_agents = [line.strip() for line in f.readlines() if line.strip()]

    # Số lượng worker (luồng) và thời gian ngủ
    total_workers = 60  # Số lượng luồng
    sleep_time = 60  # Thời gian ngủ giữa các lần gọi ping

    tasks = []
    for worker_id in range(total_workers):
        tasks.append(start_worker(user_id, proxies, user_agents, worker_id, total_workers, sleep_time))

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    # Khởi tạo ThreadPoolExecutor để chạy với asyncio
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        loop.run_until_complete(main())