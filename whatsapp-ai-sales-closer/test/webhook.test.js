import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { extractTextMessages, verifyMetaSignature } from "../src/webhook.js";

test("extractTextMessages reads all batched text messages and ignores statuses/media", () => {
  const payload = {
    object: "whatsapp_business_account",
    entry: [{ changes: [
      { field: "messages", value: { messages: [
        { id: "wamid.1", from: "923001234567", type: "text", text: { body: "  Hello  " } },
        { id: "wamid.2", from: "923001234567", type: "image", image: { id: "media" } }
      ] } },
      { field: "messages", value: { statuses: [{ id: "wamid.out" }] } }
    ] }]
  };

  assert.deepEqual(extractTextMessages(payload), [{
    id: "wamid.1",
    phoneNumber: "923001234567",
    text: "Hello",
    timestamp: null
  }]);
});

test("extractTextMessages rejects unrelated webhook objects", () => {
  assert.deepEqual(extractTextMessages({ object: "page", entry: [] }), []);
});

test("verifyMetaSignature validates the raw request body", () => {
  const secret = "app-secret";
  const body = Buffer.from('{"object":"whatsapp_business_account"}');
  const signature = `sha256=${crypto.createHmac("sha256", secret).update(body).digest("hex")}`;
  assert.equal(verifyMetaSignature(body, signature, secret), true);
  assert.equal(verifyMetaSignature(Buffer.from("tampered"), signature, secret), false);
  assert.equal(verifyMetaSignature(body, "invalid", secret), false);
});
