// Log posting is only required for the Spolm hosted platform (tryspolm.com).
// For self-hosted deployments, set SPOLM_BASE_URL to your own backend URL.
const BASE_URL = process.env.SPOLM_BASE_URL || "https://api.tryspolm.com";

async function postLog(apiKey, agentID, log) {
  try {
    const payload = {
      agentId: agentID,
      logData: log,
    };
    const res = await fetch(`${BASE_URL}/api/logs/post`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      return { valid: true, data };
    }

    let errorBody = null;
    try {
      errorBody = await res.json();
    } catch (parseErr) {
      errorBody = await res.text().catch(() => null);
    }

    console.warn("postLog failed response:", res.status, errorBody);
    return { valid: false, message: errorBody?.message || `HTTP ${res.status}` };
  } catch (err) {
    console.error("postLog error:", err);
    return { valid: false, message: err.message };
  }
}

module.exports = { postLog };
