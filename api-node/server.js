'use strict';
const express = require('express');
const { Pool } = require('pg');
const fs = require('node:fs');

function createApp(db) {
  const app = express();
  app.get('/ping', (_, res) => res.type('text').send('pong'));
  app.get('/', async (_, res) => {
    try {
      const result = await db.query('SELECT NOW() AS now');
      res.json({ api: 'node', now: result.rows[0].now });
    } catch (_) {
      res.status(503).json({ error: 'database unavailable' });
    }
  });
  app.get('/ready', async (_, res) => {
    try { await db.query('SELECT 1'); res.send('ready'); }
    catch (_) { res.status(503).send('database unavailable'); }
  });
  return app;
}
if (require.main === module) {
  const connectionString = process.env.DATABASE_URL || (process.env.DATABASE_URL_FILE && fs.readFileSync(process.env.DATABASE_URL_FILE, 'utf8').trim());
  if (!connectionString) throw new Error('Set DATABASE_URL or DATABASE_URL_FILE');
  const db = new Pool({ connectionString, connectionTimeoutMillis: 3000, query_timeout: 3000 });
  db.on('error', () => console.error('Database pool connection failed'));
  const server = createApp(db).listen(process.env.PORT || 3000, '0.0.0.0', () => console.log('Node API ready'));
  for (const signal of ['SIGINT','SIGTERM']) process.on(signal, () => server.close(() => db.end()));
}
module.exports = { createApp };
