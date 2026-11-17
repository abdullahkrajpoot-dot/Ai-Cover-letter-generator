import crypto from "node:crypto";

export function verifyMetaSignature(rawBody, signatureHeader, appSecret) {
  if (!appSecret) return true;
  if (!rawBody || !signatureHeader?.startsWith("sha256=")) return false;

  const expected = `sha256=${crypto
    .createHmac("sha256", appSecret)
    .update(rawBody)
    .digest("hex")}`;
  const provided = Buffer.from(signatureHeader);
  const calculated = Buffer.from(expected);
  return provided.length === calculated.length && crypto.timingSafeEqual(provided, calculated);
}

export function extractTextMessages(payload) {
  if (payload?.object !== "whatsapp_business_account") return [];

  return (payload.entry || []).flatMap((entry) =>
    (entry.changes || []).flatMap((change) => {
      if (change.field !== "messages") return [];
      return (change.value?.messages || [])
        .filter((message) => message.type === "text" && message.text?.body?.trim())
        .map((message) => ({
          id: message.id,
          phoneNumber: message.from,
          text: message.text.body.trim(),
          timestamp: message.timestamp || null
        }));
    })
  );
}
