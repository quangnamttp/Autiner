// index.js
import express from 'express';
import { startMorningTasks } from './src/scheduler/morningTasks.js';

const app = express();
const PORT = process.env.PORT || 3000;

// Ping check
app.get('/', (req, res) => {
  res.send('Autiner bot is running');
});

// Khởi động cron gửi tin
startMorningTasks();

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
