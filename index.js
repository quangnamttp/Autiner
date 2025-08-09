import 'dotenv/config';
import { startServer } from './src/server.js';
import { initDb } from './src/storage/db.js';

const port = process.env.PORT || 3000;

(async () => {
  await initDb(); // tạo bảng config/audit nếu chưa có
  await startServer(port);
  console.log(`[autiner] server listening on :${port}`);
})();
