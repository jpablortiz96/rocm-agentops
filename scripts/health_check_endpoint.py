#!/usr/bin/env python
"""Health-check an OpenAI-compatible endpoint."""

import argparse
import sys

import requests


def main():
    parser = argparse.ArgumentParser(
        description="Health-check an OpenAI-compatible endpoint"
    )
    parser.add_argument(
        "--base-url", required=True, help="Endpoint base URL (e.g. http://host:8000/v1)"
    )
    parser.add_argument(
        "--api-key", default="", help="API key (optional for endpoints without auth)"
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    url = f"{base_url}/models"
    headers = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        print(f"Endpoint reachable: {base_url}")
        print(f"Available models ({len(models)}):")
        for m in models:
            print(f"  - {m.get('id', 'unknown')}")
        sys.exit(0)
    except requests.RequestException as exc:
        print(f"Endpoint unreachable: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
