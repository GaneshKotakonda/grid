import { afterAll, beforeAll, expect, test } from 'vitest';
import { createServer } from 'vite';

let server;
let origin;

beforeAll(async () => {
  server = await createServer({ server: { port: 0, host: '127.0.0.1' } });
  await server.listen();
  origin = `http://127.0.0.1:${server.httpServer.address().port}`;
});

afterAll(async () => {
  await server?.close();
});

test('serves the hero image instead of forwarding it to the grid API', async () => {
  const response = await fetch(`${origin}/gridresilience-hero.png`);
  expect(response.status).toBe(200);
  expect(response.headers.get('content-type')).toContain('image/png');
  const bytes = new Uint8Array(await response.arrayBuffer());
  expect(Array.from(bytes.slice(0, 8))).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
});
