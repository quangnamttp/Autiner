import express from 'express';
import { getOnusMeta, getOnusSnapshotCached } from '../sources/onus/cache.js';

const router = express.Router();

router.get('/debug/onus', async (req, res) => {
  try {
    const meta = getOnusMeta();
    const rows = await getOnusSnapshotCached({ maxAgeSec: 3600 });
    res.json({
      meta,
      count: rows.length,
      sample: rows.slice(0, 5) // xem 5 bản ghi đầu
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

export default router;
