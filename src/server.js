import express from 'express';
import { router } from './routes.js';
import { logger } from './utils/logger.js';

export async function startServer(port) {
  const app = express();
  app.use(express.json({ limit: '1mb' }));

  // simple request log
  app.use((req, _res, next) => {
    logger.info(`${req.method} ${req.url}`);
    next();
  });

  // health endpoint for UptimeRobot
  app.get('/health', (_req, res) => res.status(200).send('OK'));

  app.use(router);

  return new Promise((resolve) => {
    app.listen(port, () => resolve());
  });
}
