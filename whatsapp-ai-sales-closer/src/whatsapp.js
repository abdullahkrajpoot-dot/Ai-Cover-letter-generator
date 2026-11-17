import axios from "axios";

export function createWhatsAppClient(config) {
  const client = axios.create({
    baseURL: `https://graph.facebook.com/${config.graphApiVersion}`,
    timeout: 15000,
    headers: {
      Authorization: `Bearer ${config.whatsappToken}`,
      "Content-Type": "application/json"
    }
  });

  async function sendText(to, body) {
    try {
      const { data } = await client.post(`/${config.phoneNumberId}/messages`, {
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to,
        type: "text",
        text: { preview_url: false, body }
      });
      return data?.messages?.[0]?.id || null;
    } catch (error) {
      const details = error.response?.data?.error || error.message;
      throw new Error(`WhatsApp send failed: ${JSON.stringify(details)}`);
    }
  }

  return { sendText };
}
