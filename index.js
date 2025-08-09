import 'dotenv/config';
import { startServer } from './src/server.js';
import { initDb } from './src/storage/db.js';
import { startSchedulers } from './src/scheduler/index.js';

const port = process.env.PORT || 3000;

(async () => {
  await initDb();
  await startServer(port);
  startSchedulers(); // cron cố định
  console.log(`[autiner] server listening on :${port}`);
})();
