const required = [
  "VERIFY_TOKEN",
  "WHATSAPP_TOKEN",
  "PHONE_NUMBER_ID",
  "GEMINI_API_KEY",
  "SUPABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY"
];

export function loadConfig(env = process.env) {
  const missing = required.filter((name) => !env[name]?.trim());
  if (missing.length) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
  }

  const port = Number(env.PORT || 3000);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("PORT must be an integer between 1 and 65535");
  }

  return Object.freeze({
    port,
    nodeEnv: env.NODE_ENV || "development",
    verifyToken: env.VERIFY_TOKEN,
    whatsappToken: env.WHATSAPP_TOKEN,
    phoneNumberId: env.PHONE_NUMBER_ID,
    metaAppSecret: env.META_APP_SECRET || "",
    graphApiVersion: env.GRAPH_API_VERSION || "v20.0",
    geminiApiKey: env.GEMINI_API_KEY,
    geminiModel: env.GEMINI_MODEL || "gemini-2.5-flash",
    supabaseUrl: env.SUPABASE_URL,
    supabaseServiceRoleKey: env.SUPABASE_SERVICE_ROLE_KEY,
    agencyName: env.AGENCY_NAME || "Our Digital Agency",
    discoveryCallUrl: env.DISCOVERY_CALL_URL || ""
  });
}
