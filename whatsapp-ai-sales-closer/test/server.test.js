import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { once } from "node:events";
import { createApp } from "../server.js";

test("webhook verifies, acknowledges, and processes a signed text message", async (t) => {
  const config = { verifyToken: "verify-me", metaAppSecret: "secret" };
  let processed;
  const completed = new Promise((resolve) => { processed = resolve; });
  const services = {
    store: {
      claimMessage: async () => true,
      getHistory: async () => [],
      saveExchange: async (exchange) => processed(exchange)
    },
    ai: { generateReply: async () => "How soon would you like to launch?" },
    whatsapp: { sendText: async () => "wamid.outbound" }
  };
  const server = createApp(config, services).listen(0, "127.0.0.1");
  t.after(() => server.close());
  await once(server, "listening");
  const { port } = server.address();
  const baseUrl = `http://127.0.0.1:${port}`;

  const verification = await fetch(`${baseUrl}/webhook?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=12345`);
  assert.equal(verification.status, 200);
  assert.equal(await verification.text(), "12345");

  const payload = JSON.stringify({
    object: "whatsapp_business_account",
    entry: [{ changes: [{ field: "messages", value: { messages: [{
      id: "wamid.inbound",
      from: "923001234567",
      type: "text",
      text: { body: "I need a web store" }
    }] } }] }]
  });
  const signature = `sha256=${crypto.createHmac("sha256", config.metaAppSecret).update(payload).digest("hex")}`;
  const response = await fetch(`${baseUrl}/webhook`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-hub-signature-256": signature },
    body: payload
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await completed, {
    phoneNumber: "923001234567",
    incoming: "I need a web store",
    reply: "How soon would you like to launch?"
  });
});
