import requests
import json

# Log posting is only required for the Spolm hosted platform (tryspolm.com).
# For self-hosted deployments, pass base_url to Tracer() or set SPOLM_BASE_URL.
def post_log(api_key, agent_id, log, base_url: str = "https://api.tryspolm.com"):
    try:
        payload = {
            "agentId": agent_id,
            "logData": log,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        res = requests.post(
            f"{base_url}/api/logs/post",
            json=payload,
            headers=headers,
            timeout=10,
        )

        if res.ok:
            data = res.json()
            return {"valid": True, "data": data}

        try:
            error_body = res.json()
        except ValueError:
            error_body = res.text

        print("post_log failed response:", res.status_code, error_body)
        return {
            "valid": False,
            "message": (
                error_body.get("message")
                if isinstance(error_body, dict)
                else f"HTTP {res.status_code}"
            ),
        }

    except Exception as err:
        print("post_log error:", err)
        return {"valid": False, "message": str(err)}
