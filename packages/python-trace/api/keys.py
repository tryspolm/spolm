import requests

# API key validation is only required for the Spolm hosted platform (tryspolm.com).
# For self-hosted deployments, pass base_url to Tracer() or set SPOLM_BASE_URL.
def check_api_key(api_key: str, base_url: str = "https://api.tryspolm.com") -> dict:
    try:
        res = requests.get(
            f"{base_url}/api/keys/validate",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )

        if res.ok:
            data = res.json()
            return {
                "valid": True,
                "data": data,
            }
        else:
            error = res.json()
            print("Invalid API Key")
            return {
                "valid": False,
                "message": error.get("message", "Invalid API key"),
            }

    except requests.RequestException as err:
        print("Error checking API key:", err)
        return {
            "valid": False,
            "message": "Failed to validate API key",
        }
