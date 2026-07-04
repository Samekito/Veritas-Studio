/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string;
  readonly VITE_CUSTOMER_URL: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
