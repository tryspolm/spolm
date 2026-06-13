// API key validation is only required for the Spolm hosted platform (tryspolm.com).
// For self-hosted deployments, pass baseUrl to Tracer() or set SPOLM_BASE_URL.
async function checkAPIKey(apiKey, baseUrl = "https://api.tryspolm.com") {
  try {
    const res = await fetch(`${baseUrl}/api/keys/validate`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
    });

    if (res.ok) {
      const data = await res.json();
      return {
        valid: true,
        data: data,
      };
    } else {
      const error = await res.json();
      console.log("Invalid API Key");
      return {
        valid: false,
        message: error.message || "Invalid API key",
      };
    }
  } catch (err) {
    console.error("Error checking API key:", err);
    return {
      valid: false,
      message: "Failed to validate API key",
    };
  }
}

module.exports = { checkAPIKey };
