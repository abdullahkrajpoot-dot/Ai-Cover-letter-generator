import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.js";

const valid = {
  VERIFY_TOKEN: "verify",
  WHATSAPP_TOKEN: "whatsapp",
  PHONE_NUMBER_ID: "123",
  GEMINI_API_KEY: "gemini",
  SUPABASE_URL: "https://example.supabase.co",
  SUPABASE_SERVICE_ROLE_KEY: "supabase"
};

test("loadConfig supplies safe defaults", () => {
  const config = loadConfig(valid);
  assert.equal(config.port, 3000);
  assert.equal(config.geminiModel, "gemini-2.5-flash");
  assert.equal(config.graphApiVersion, "v20.0");
});

test("loadConfig reports every missing required setting", () => {
  assert.throws(() => loadConfig({}), /VERIFY_TOKEN.*SUPABASE_SERVICE_ROLE_KEY/);
});
