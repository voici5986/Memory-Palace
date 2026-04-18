/// <reference types="vite/client" />

interface MemoryPalaceRuntimeConfig {
  maintenanceApiKey?: string;
  maintenanceApiKeyMode?: string;
  mcpApiKey?: string;
  mcpApiKeyMode?: string;
}

interface NavigatorUADataBrand {
  brand?: string;
  version?: string;
}

interface NavigatorUAData {
  brands?: NavigatorUADataBrand[];
  mobile?: boolean;
  platform?: string;
}

interface Navigator {
  userAgentData?: NavigatorUAData;
}

interface Window {
  __MEMORY_PALACE_RUNTIME__?: MemoryPalaceRuntimeConfig;
  __MCP_RUNTIME_CONFIG__?: MemoryPalaceRuntimeConfig;
}
