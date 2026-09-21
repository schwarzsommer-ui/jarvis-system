// Placeholder configuration only. Put real values in Netlify Environment Variables.
// Never commit API keys to this file.
const aiServices = {
  gemini: {
    name: "Gemini Flash",
    keyEnv: "GEMINI_API_KEY",
    endpointEnv: "GEMINI_API_URL",
    endpointPlaceholder: "https://generativelanguage.googleapis.com/v1beta/models",
    modelEnv: "GEMINI_MODEL",
    modelPlaceholder: "gemini-2.5-flash"
  },
  gpt: {
    name: "GPT-4o mini",
    keyEnv: "GPT_API_KEY",
    endpointEnv: "GPT_API_URL",
    endpointPlaceholder: "https://api.openai.com/v1/chat/completions",
    modelEnv: "GPT_MODEL",
    modelPlaceholder: "gpt-4o-mini"
  },
  nim: {
    name: "NVIDIA NIM",
    keyEnv: "NIM_API_KEY",
    endpointEnv: "NIM_API_URL",
    endpointPlaceholder: "https://integrate.api.nvidia.com/v1/chat/completions",
    modelEnv: "NIM_MODEL",
    modelPlaceholder: "meta/llama-3.1-8b-instruct"
  }
};

module.exports = aiServices;
