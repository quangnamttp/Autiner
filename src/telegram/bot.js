// src/telegram/bot.js
import TelegramBot from 'node-telegram-bot-api';

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;

if (!TOKEN) throw new Error('⚠️ TELEGRAM_BOT_TOKEN chưa được cấu hình!');
if (!CHAT_ID) throw new Error('⚠️ ALLOWED_TELEGRAM_USER_ID chưa được cấu hình!');

export const bot = new TelegramBot(TOKEN, { polling: false });

export async function sendMessage(chatId, text) {
  try {
    await bot.sendMessage(chatId, text, { parse_mode: 'HTML' });
  } catch (err) {
    console.error('[ERROR] sendMessage:', err);
  }
}

export function sendToOwner(text) {
  return sendMessage(CHAT_ID, text);
}
