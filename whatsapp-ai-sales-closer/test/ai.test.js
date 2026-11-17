import test from "node:test";
import assert from "node:assert/strict";
import { fallbackReply } from "../src/ai.js";

test("fallbackReply matches English, Urdu, and Roman Urdu", () => {
  assert.match(fallbackReply("I need an ecommerce website"), /^Thanks/);
  assert.match(fallbackReply("مجھے ویب سائٹ چاہیے"), /رابطہ/);
  assert.match(fallbackReply("Mujhe website banwani hai"), /^Rabta/);
});
