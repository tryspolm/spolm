// Log posting is only required for the Spolm hosted platform (tryspolm.com).
// For self-hosted deployments, pass baseUrl to Tracer() or set SPOLM_BASE_URL.
async function postLog(apiKey, agentID, log, baseUrl = "https://api.tryspolm.com") {
  try {
    const payload = {
      agentId: agentID,
      logData: log,
    };
    const res = await fetch(`${baseUrl}/api/logs/post`, {
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
