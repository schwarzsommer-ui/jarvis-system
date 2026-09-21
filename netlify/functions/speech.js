const headers = {
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json"
};

function json(statusCode, body) {
  return { statusCode, headers, body: JSON.stringify(body) };
}

async function findGermanVoice(apiKey) {
  const response = await fetch("https://api.elevenlabs.io/v1/voices", {
    headers: { Accept: "application/json", "xi-api-key": apiKey }
  });
  if (!response.ok) return null;
  const data = await response.json();
  const voices = Array.isArray(data.voices) ? data.voices : [];
  const german = voices.find((voice) => {
    const labels = voice.labels || {};
    return String(labels.language || "").toLowerCase().startsWith("de")
      || /german|deutsch/i.test(String(voice.name || ""));
  });
  return german?.voice_id || voices[0]?.voice_id || null;
}

async function requestSpeech(apiKey, voiceId, text) {
  return fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(voiceId)}`, {
    method: "POST",
    headers: {
      Accept: "audio/mpeg",
      "Content-Type": "application/json",
      "xi-api-key": apiKey
    },
    body: JSON.stringify({
      text,
      model_id: process.env.ELEVENLABS_MODEL_ID || "eleven_multilingual_v2",
      language_code: "de",
      voice_settings: {
        stability: 0.62,
        similarity_boost: 0.78,
        style: 0.18,
        use_speaker_boost: true
      }
    })
  });
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return { statusCode: 204, headers, body: "" };
  if (event.httpMethod !== "POST") return json(405, { error: "POST erforderlich." });

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return json(400, { error: "Der Request-Body muss gültiges JSON sein." });
  }
  const text = typeof payload.text === "string" ? payload.text.trim() : "";
  if (!text) return json(400, { error: "text ist erforderlich." });
  if (text.length > 12000) return json(413, { error: "text darf höchstens 12.000 Zeichen enthalten." });

  const apiKey = process.env.ELEVENLABS_API_KEY;
  const voiceId = process.env.ELEVENLABS_VOICE_ID || "ErXwobaYiN019PkySvjV";
  if (!apiKey) {
    return json(503, { error: "ElevenLabs ist nicht konfiguriert.", configured: false });
  }

  let response;
  let initialStatus = null;
  let fallbackStatus = null;
  try {
    response = await requestSpeech(apiKey, voiceId, text);
    initialStatus = response.status;
    if (!response.ok) {
      const fallbackVoiceId = await findGermanVoice(apiKey);
      if (fallbackVoiceId && fallbackVoiceId !== voiceId) {
        response = await requestSpeech(apiKey, fallbackVoiceId, text);
        fallbackStatus = response.status;
      }
    }
  } catch (error) {
    console.error("ElevenLabs request failed", error);
    return json(502, { error: "ElevenLabs ist momentan nicht erreichbar." });
  }

  if (!response.ok) {
    console.error("ElevenLabs API error", {
      initialStatus,
      fallbackStatus,
      finalStatus: response.status
    });
    return json(502, {
      error: "ElevenLabs konnte die Sprache nicht erzeugen.",
      upstreamStatus: response.status
    });
  }

  const audio = Buffer.from(await response.arrayBuffer());
  return {
    statusCode: 200,
    headers: {
      ...headers,
      "Cache-Control": "no-store",
      "Content-Type": "audio/mpeg"
    },
    isBase64Encoded: true,
    body: audio.toString("base64")
  };
};
