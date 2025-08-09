import axios from 'axios';
import { logger } from '../utils/logger.js';

const BOT_TOKEN = process.env.BOT_TOKEN;
const api = axios.create({
  baseURL: `https://api.telegram.org/bot${BOT_TOKEN}/`,
  timeout: 10000
});

export async function setWebhook(url) {
  try {
    const { data } = await api.post('setWebhook', {
      url,
      drop_pending_updates: true,
      allowed_updates: ['message','callback_query']
    });
    logger.info('setWebhook', data);
    return data;
  } catch (err) {
    logger.error('setWebhook', err?.response?.data || err.message);
  }
}

export async function sendMessage(chat_id, text, opts = {}) {
  try {
    // ÉP parse_mode = HTML kể cả nếu opts có parse_mode khác
    const payload = {
      chat_id,
      text,
      ...opts,
      parse_mode: 'HTML',
      disable_web_page_preview: true
    };
    const { data } = await api.post('sendMessage', payload);
    return data;
  } catch (err) {
    logger.error('sendMessage', err?.response?.data || err.message);
  }
}

export async function answerCallbackQuery(callback_query_id) {
  try {
    await api.post('answerCallbackQuery', { callback_query_id });
  } catch (err) {
    logger.error('answerCallbackQuery', err?.response?.data || err.message);
  }
}

export async function handleUpdate(update) {
  try {
    const hasMsg = update.message || update.callback_query;
    if (hasMsg) {
      const { handleMessageOrCallback } = await import('./handler.js');
      await handleMessageOrCallback(update);
    }
  } catch (err) {
    logger.error('handleUpdate', err);
  }
}
