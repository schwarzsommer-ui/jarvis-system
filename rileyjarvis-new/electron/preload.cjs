const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ricky", {
  createRealtimeToken: () => ipcRenderer.invoke("realtime:create-token"),
  hasOpenAIKey: () => ipcRenderer.invoke("realtime:has-key"),
  localChat: (message) => ipcRenderer.invoke("local:chat", message),
  executeTool: (toolCall) => ipcRenderer.invoke("tools:execute", toolCall),
  getToolSpecs: () => ipcRenderer.invoke("tools:list"),
});
