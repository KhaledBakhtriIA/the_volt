import concurrent.futures
import requests
import time
import random
from datetime import datetime, timezone

URL = "http://127.0.0.1:8060/stream/ingest"

def send_request(i):
    payload = {
        "symbol": random.choice(["BTC", "ETH", "SOL", "ADA"]),
        "price": random.uniform(100.0, 60000.0),
        "volume": random.uniform(0.1, 10.0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "trade"
    }
    try:
        r = requests.post(URL, json=payload, timeout=5.0)
        return r.status_code, r.json()
    except Exception as e:
        return str(e), None

def main():
    requests_to_send = 250
    print(f"Starting stress test: {requests_to_send} requests to {URL}...")
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(send_request, range(requests_to_send)))
    
    end = time.time()
    success_count = sum(1 for r, j in results if r == 200)
    
    print(f"Test completed in {end - start:.2f} seconds.")
    print(f"Successful requests: {success_count}/{requests_to_send}")
    
    # Print the last queued count to see how buffer is doing
    successful_jsons = [j for r, j in results if r == 200 and j]
    if successful_jsons:
        print(f"Last reported buffer queue size: {successful_jsons[-1].get('queued')}")

    if success_count < requests_to_send:
        errors = [r for r, j in results if r != 200]
        print(f"Sample errors: {errors[:5]}")

if __name__ == "__main__":
    main()
