const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('./server');
test('database time, health, readiness, unavailable database', async () => {
  let fail = false;
  const server = createApp({query: async sql => {
    if (fail) throw new Error('private credentials must not leak');
    assert.ok(['SELECT NOW() AS now', 'SELECT 1'].includes(sql));
    return {rows:[{now:'2026-01-01T00:00:00.000Z'}]};
  }}).listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    assert.deepEqual(await (await fetch(base)).json(), {api:'node',now:'2026-01-01T00:00:00.000Z'});
    assert.equal(await (await fetch(base+'/ping')).text(), 'pong');
    assert.equal((await fetch(base+'/ready')).status, 200);
    fail = true;
    assert.equal((await fetch(base+'/ready')).status, 503);
    const response = await fetch(base); assert.equal(response.status,503);
    assert.deepEqual(await response.json(),{error:'database unavailable'});
  } finally { await new Promise(resolve => server.close(resolve)); }
});
