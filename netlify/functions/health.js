const headers = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store"
};

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: "Methode nicht erlaubt. Verwende GET." })
    };
  }

  return {
    statusCode: 200,
    headers,
    body: JSON.stringify({
      status: "ok",
      service: "jarvis-agent",
      safeMode: true,
      claudeConfigured: Boolean(process.env.CLAUDE_API_KEY),
      geminiConfigured: Boolean(process.env.GEMINI_API_KEY),
      nimConfigured: Boolean(process.env.NIM_API_KEY && process.env.NIM_API_URL),
      ollamaConfigured: Boolean(process.env.OLLAMA_URL || process.env.JARVIS_PROVIDER === "ollama"),
      makeConfigured: Boolean(process.env.MAKE_WEBHOOK_URL),
      monitoringConfigured: Boolean(process.env.MARKET_DATA_API_KEY),
      accessControlConfigured: Boolean(process.env.JARVIS_ACCESS_TOKEN),
      runnerConfigured: Boolean(process.env.JARVIS_RUNNER_URL && process.env.JARVIS_RUNNER_TOKEN),
      storageConfigured: Boolean(process.env.JARVIS_DATABASE_URL),
      elevenLabsConfigured: Boolean(process.env.ELEVENLABS_API_KEY),
      timestamp: new Date().toISOString()
    })
  };
};
