import threading
import time
import uuid
import cloudscraper
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

# Constants
PING_INTERVAL = 0
RETRIES = 1000

DOMAIN_API = {
    "SESSION": "http://18.136.143.169/api/auth/session",
    "PING": "http://13.215.134.222/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}  

# Logger Configuration
logger.remove()  # Remove default handler
logger.add(lambda msg: print(msg, end=""), level="INFO")  # Only print INFO level messages

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

def call_api(url, data, proxy, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://app.nodepay.ai",
    }

    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.post(url, json=data, headers=headers, proxies={
                                "http": proxy, "https": proxy}, timeout=30)

        response.raise_for_status()
        return valid_resp(response.json())
    except Exception:
        raise ValueError(f"Failed API call to {url}")

def start_ping(proxy, token):
    global last_ping_time, RETRIES, status_connect

    while True:
        current_time = time.time()
        if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
            time.sleep(PING_INTERVAL)
            continue

        last_ping_time[proxy] = current_time

        try:
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time())
            }

            response = call_api(DOMAIN_API["PING"], data, proxy, token)
            if response["code"] == 0:
                logger.info(f"Ping sent successfully via proxy {proxy}: {response}")
                RETRIES = 0
                status_connect = CONNECTION_STATES["CONNECTED"]
            else:
                handle_ping_fail(proxy, response)
        except Exception:
            handle_ping_fail(proxy, None)

        time.sleep(PING_INTERVAL)

def handle_ping_fail(proxy, response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy):
    global status_connect, account_info
    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    logger.info(f"Logged out and cleared session info for proxy {proxy}")

def render_profile_info(proxy, token):
    global browser_id, account_info

    try:
        np_session_info = load_session_info(proxy)
        if not np_session_info:
            browser_id = uuidv4()
            response = call_api(DOMAIN_API["SESSION"], {}, proxy, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                start_ping(proxy, token)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            start_ping(proxy, token)
    except Exception:
        pass  # Suppress errors to focus only on ping messages

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def load_tokens(token_file):
    try:
        with open(token_file, 'r') as file:
            tokens = [line.strip() for line in file if line.strip()]
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")

def load_session_info(proxy):
    return {}

def save_session_info(proxy, data):
    pass

def is_valid_proxy(proxy):
    return True

def run_for_token(token, all_proxies):
    while True:  # Continuous loop to keep reloading proxies
        try:
            all_proxies = load_proxies('proxies.txt')
            if not all_proxies:
                break

            with ThreadPoolExecutor(max_workers=100) as executor:
                active_proxies = [proxy for proxy in all_proxies if is_valid_proxy(proxy)][:1000]
                future_to_proxy = {executor.submit(render_profile_info, proxy, token): proxy for proxy in active_proxies}

                for future in future_to_proxy:
                    try:
                        future.result()
                    except Exception:
                        pass  # Suppress errors to focus only on ping messages

        except Exception:
            break

def main():
    all_proxies = load_proxies('proxies.txt')
    tokens = load_tokens('token.txt')

    threads = []
    for token in tokens:
        thread = threading.Thread(target=run_for_token, args=(token, all_proxies))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

def load_user_agents(user_file):
    try:
        with open(user_file, 'r') as file:
            user_agents = [line.strip() for line in file if line.strip()]
        return user_agents
    except Exception as e:
        logger.error(f"Failed to load user agents: {e}")
        raise SystemExit("Exiting due to failure in loading user agents")

def assign_proxies_to_user_agents(user_agents, proxies, group_size=10):
    assigned = {}
    for i, user_agent in enumerate(user_agents):
        start = i * group_size
        end = start + group_size
        assigned[user_agent] = proxies[start:end]
    return assigned

def render_profile_info_with_user_agent(proxy, token, user_agent):
    global browser_id, account_info

    headers = {
        "User-Agent": user_agent
    }

    try:
        np_session_info = load_session_info(proxy)
        if not np_session_info:
            browser_id = uuidv4()
            response = call_api(DOMAIN_API["SESSION"], {}, proxy, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                start_ping(proxy, token)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            start_ping(proxy, token)
    except Exception:
        pass  # Suppress errors to focus only on ping messages

def run_for_token_with_user_agents(token, assigned_proxies):
    for user_agent, proxies in assigned_proxies.items():
        with ThreadPoolExecutor(max_workers=len(proxies)) as executor:
            future_to_proxy = {
                executor.submit(render_profile_info_with_user_agent, proxy, token, user_agent): proxy
                for proxy in proxies
            }
            for future in future_to_proxy:
                try:
                    future.result()
                except Exception:
                    pass  # Suppress errors to focus only on ping messages

def main():
    all_proxies = load_proxies('proxies.txt')
    tokens = load_tokens('token.txt')
    user_agents = load_user_agents('user.txt')

    if not all_proxies or not user_agents:
        logger.error("No proxies or user agents loaded.")
        return

    assigned_proxies = assign_proxies_to_user_agents(user_agents, all_proxies, group_size=10)

    threads = []
    for token in tokens:
        thread = threading.Thread(target=run_for_token_with_user_agents, args=(token, assigned_proxies))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == '__main__':
    main()