import requests
import time
import concurrent.futures

BASE_URL = "http://localhost:8080/universities"

def test_endpoint():
    try:
        start_time = time.time()
        response = requests.get(BASE_URL, timeout=5)
        duration = time.time() - start_time
        return response.status_code, duration
    except Exception as e:
        return None, str(e)

def run_performance_test(concurrent_requests=10):
    print(f"Starting performance test: {concurrent_requests} concurrent requests to {BASE_URL}")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [executor.submit(test_endpoint) for _ in range(concurrent_requests)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    successes = [r for r in results if r[0] == 200]
    durations = [r[1] for r in results if isinstance(r[1], float)]
    
    print("\nResults:")
    print(f"Total Requests: {len(results)}")
    print(f"Successful Requests: {len(successes)}")
    if durations:
        print(f"Average Latency: {sum(durations)/len(durations):.4f}s")
        print(f"Max Latency: {max(durations):.4f}s")
        print(f"Min Latency: {min(durations):.4f}s")
    else:
        print("No successful requests to measure latency.")

if __name__ == "__main__":
    run_performance_test(20)
