import "dotenv/config";
import express from "express";
import { fileURLToPath } from "node:url";
import { loadConfig } from "./src/config.js";
import { createStore } from "./src/store.js";
import { createSalesAI, fallbackReply } from "./src/ai.js";
import { createWhatsAppClient } from "./src/whatsapp.js";
import { extractTextMessages, verifyMetaSignature } from "./src/webhook.js";

export function createApp(config, services) {
  const app = express();
  const phoneQueues = new Map();

  app.disable("x-powered-by");
  app.use(express.json({
    limit: "256kb",
    verify: (req, _res, buffer) => { req.rawBody = Buffer.from(buffer); }
  }));

  app.get("/", (_req, res) => res.status(200).json({ status: "ok" }));
  app.get("/health", (_req, res) => res.status(200).json({ status: "healthy" }));

  app.get("/webhook", (req, res) => {
    const mode = req.query["hub.mode"];
    const token = req.query["hub.verify_token"];
    const challenge = req.query["hub.challenge"];
    if (mode === "subscribe" && token === config.verifyToken && challenge) {
      console.info("[webhook] Meta verification succeeded");
      return res.status(200).send(challenge);
    }
    console.warn("[webhook] Meta verification rejected");
    return res.sendStatus(403);
  });

  async function processMessage(message) {
    const claimed = await services.store.claimMessage(message);
    if (!claimed) {
      console.info(`[message:${message.id}] duplicate ignored`);
      return;
    }

    console.info(`[message:${message.id}] processing lead ${message.phoneNumber}`);
    const history = await services.store.getHistory(message.phoneNumber, 8);
    let reply;
    try {
      reply = await services.ai.generateReply(history, message.text);
    } catch (error) {
      console.error(`[message:${message.id}] Gemini error`, error);
      reply = fallbackReply(message.text);
    }
    await services.store.saveExchange({
      phoneNumber: message.phoneNumber,
      incoming: message.text,
      reply
    });
    const outboundId = await services.whatsapp.sendText(message.phoneNumber, reply);
    console.info(`[message:${message.id}] reply sent${outboundId ? ` as ${outboundId}` : ""}`);
  }

  function enqueue(message) {
    const previous = phoneQueues.get(message.phoneNumber) || Promise.resolve();
    const current = previous
      .catch(() => undefined)
      .then(() => processMessage(message))
      .catch((error) => console.error(`[message:${message.id}] processing failed`, error))
      .finally(() => {
        if (phoneQueues.get(message.phoneNumber) === current) {
          phoneQueues.delete(message.phoneNumber);
        }
      });
    phoneQueues.set(message.phoneNumber, current);
  }

  app.post("/webhook", (req, res) => {
    const signature = req.get("x-hub-signature-256");
    if (!verifyMetaSignature(req.rawBody, signature, config.metaAppSecret)) {
      console.warn("[webhook] invalid Meta signature");
      return res.sendStatus(401);
    }

    const messages = extractTextMessages(req.body);
    res.sendStatus(200);
    for (const message of messages) enqueue(message);
    if (messages.length) console.info(`[webhook] accepted ${messages.length} text message(s)`);
  });

  app.use((error, _req, res, _next) => {
    console.error("[server] request error", error);
    if (!res.headersSent) res.status(400).json({ error: "Invalid request" });
  });
  return app;
}

export function start() {
  const config = loadConfig();
  if (config.nodeEnv === "production" && !config.metaAppSecret) {
    throw new Error("META_APP_SECRET is required in production to verify webhook signatures");
  }
  const app = createApp(config, {
    store: createStore(config),
    ai: createSalesAI(config),
    whatsapp: createWhatsAppClient(config)
  });
  return app.listen(config.port, () => {
    console.info(`[server] listening on port ${config.port} (${config.nodeEnv})`);
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const server = start();
    const shutdown = (signal) => {
      console.info(`[server] ${signal} received; closing gracefully`);
      server.close((error) => {
        if (error) {
          console.error("[server] graceful shutdown failed", error);
          process.exitCode = 1;
        }
      });
    };
    process.once("SIGTERM", () => shutdown("SIGTERM"));
    process.once("SIGINT", () => shutdown("SIGINT"));
  } catch (error) {
    console.error("[server] startup failed", error);
    process.exitCode = 1;
  }
}
