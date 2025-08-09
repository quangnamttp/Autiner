import axios from 'axios';
import { logger } from '../utils/logger.js';
import { handleMessageOrCallback } from './handler.js';

const BOT_TOKEN = process.env.BOT_TOKEN;
const api = axios.create({ baseURL: `https://api.telegram.org/bot${BOT_TOKEN}/`, timeout: 10000 });

export async function setWebhook(url) {
  const { data } = await api.post('setWebhook', {
    url, drop_pending_updates: true, allowed_updates: ['message','callback_query']
  });
  logger.info('setWebhook resp', data);
  return data;
}

export async function sendMessage(chat_id, text, opts = {}) {
  try {
    const payload = { chat_id, text, parse_mode: 'MarkdownV2', ...opts };
    const { data } = await api.post('sendMessage', payload);
    return data;
  } catch (err) {
    logger.error('sendMessage', err?.response?.data || err.message);
  }
}

export async function answerCallbackQuery(callback_query_id) {
  try { await api.post('answerCallbackQuery', { callback_query_id }); }
  catch (err) { logger.error('answerCallbackQuery', err?.response?.data || err.message); }
}

export async function handleUpdate(update) {
  try {
    if (update.message || update.callback_query) await handleMessageOrCallback(update);
    else logger.info('Unhandled update keys', Object.keys(update));
  } catch (err) { logger.error('handleUpdate', err); }
}
