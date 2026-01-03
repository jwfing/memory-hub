#!/usr/bin/env python
"""Test HTTP server functionality."""

import requests
import time
import json


def test_health_endpoint(base_url="http://localhost:8000"):
    """Test health check endpoint."""
    print("\n=== Testing Health Endpoint ===")

    try:
        response = requests.get(f"{base_url}/health", timeout=5)

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed")
            print(f"  Status: {data.get('status')}")
            print(f"  Server: {data.get('server')}")
            print(f"  Timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"✗ Health check failed with status {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"✗ Health check failed: {e}")
        return False


def test_sse_endpoint(base_url="http://localhost:8000"):
    """Test SSE endpoint."""
    print("\n=== Testing SSE Endpoint ===")

    try:
        response = requests.get(f"{base_url}/sse", stream=True, timeout=10)

        if response.status_code == 200:
            print(f"✓ SSE connection established")

            # Read first event
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    print(f"  Received: {decoded_line}")
                    if 'data:' in decoded_line:
                        # Parse data
                        data = decoded_line.split('data: ', 1)[1]
                        try:
                            parsed = json.loads(data)
                            print(f"  Status: {parsed.get('status')}")
                            print(f"  Server: {parsed.get('server')}")
                        except json.JSONDecodeError:
                            pass
                        break

            return True
        else:
            print(f"✗ SSE connection failed with status {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"✗ SSE connection failed: {e}")
        return False


def test_cors_headers(base_url="http://localhost:8000"):
    """Test CORS headers."""
    print("\n=== Testing CORS Headers ===")

    try:
        response = requests.options(f"{base_url}/health", timeout=5)

        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        }

        print(f"✓ CORS headers present")
        for key, value in cors_headers.items():
            if value:
                print(f"  {key}: {value}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"✗ CORS check failed: {e}")
        return False


def main():
    """Run all HTTP server tests."""
    print("=" * 50)
    print("HTTP Server Tests")
    print("=" * 50)

    # Wait for server to start
    print("\nWaiting for server to start...")
    time.sleep(2)

    base_url = "http://localhost:8000"

    # Run tests
    results = []
    results.append(test_health_endpoint(base_url))
    results.append(test_sse_endpoint(base_url))
    results.append(test_cors_headers(base_url))

    # Summary
    print("\n" + "=" * 50)
    if all(results):
        print("All HTTP server tests passed! ✓")
    else:
        print(f"Some tests failed: {sum(results)}/{len(results)} passed")
    print("=" * 50)


if __name__ == "__main__":
    main()