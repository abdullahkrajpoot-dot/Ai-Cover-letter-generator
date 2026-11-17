import { createClient } from "@supabase/supabase-js";

export function createStore(config) {
  const db = createClient(config.supabaseUrl, config.supabaseServiceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false }
  });

  async function claimMessage(message) {
    const { error } = await db.from("processed_messages").insert({
      message_id: message.id,
      phone_number: message.phoneNumber
    });
    if (!error) return true;
    if (error.code === "23505") return false;
    throw new Error(`Could not claim message: ${error.message}`);
  }

  async function getHistory(phoneNumber, limit = 8) {
    const { data, error } = await db
      .from("conversation_messages")
      .select("role, content, created_at")
      .eq("phone_number", phoneNumber)
      .order("created_at", { ascending: false })
      .limit(limit);
    if (error) throw new Error(`Could not load conversation: ${error.message}`);
    return (data || []).reverse();
  }

  async function saveExchange({ phoneNumber, incoming, reply }) {
    const now = new Date().toISOString();
    const { error: leadError } = await db.from("leads").upsert(
      {
        phone_number: phoneNumber,
        last_message: incoming,
        ai_reply: reply,
        updated_at: now
      },
      { onConflict: "phone_number" }
    );
    if (leadError) throw new Error(`Could not update lead: ${leadError.message}`);

    const { error: historyError } = await db.from("conversation_messages").insert([
      { phone_number: phoneNumber, role: "user", content: incoming },
      { phone_number: phoneNumber, role: "model", content: reply }
    ]);
    if (historyError) throw new Error(`Could not save conversation: ${historyError.message}`);
  }

  return { claimMessage, getHistory, saveExchange };
}
