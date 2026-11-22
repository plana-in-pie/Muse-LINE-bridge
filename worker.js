// LINE Webhook receiver for the Muse LINE bridge.
// POST /webhook : verifies X-Line-Signature, queues events into KV, returns 200.
// GET  /pending : (Bearer POLL_KEY) returns queued events.
// POST /ack     : (Bearer POLL_KEY) deletes acked events.
// Bindings: KV namespace bound as LINE_QUEUE. Secrets: LINE_CHANNEL_SECRET, POLL_KEY.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'GET' && url.pathname === '/health') {
      return new Response('ok');
    }

    if (request.method === 'POST' && url.pathname === '/webhook') {
      const body = await request.text();
      const sig = request.headers.get('x-line-signature') || '';
      const ok = await verifySignature(body, sig, env.LINE_CHANNEL_SECRET);
      if (!ok) return new Response('invalid signature', { status: 403 });
      let data;
      try {
        data = JSON.parse(body);
      } catch {
        return new Response('bad json', { status: 400 });
      }
      const events = Array.isArray(data.events) ? data.events : [];
      const now = Date.now();
      for (let i = 0; i < events.length; i++) {
        const id = `${now}-${i}-${crypto.randomUUID()}`;
        await env.LINE_QUEUE.put(
          `evt:${id}`,
          JSON.stringify({ received_at: new Date().toISOString(), event: events[i] })
        );
      }
      return new Response('ok');
    }

    if (request.method === 'GET' && url.pathname === '/pending') {
      if (!authorized(request, env)) return new Response('unauthorized', { status: 401 });
      const list = await env.LINE_QUEUE.list({ prefix: 'evt:', limit: 100 });
      const items = [];
      for (const k of list.keys) {
        const v = await env.LINE_QUEUE.get(k.name);
        if (v) items.push({ id: k.name.slice(4), payload: JSON.parse(v) });
      }
      return Response.json({ items });
    }

    if (request.method === 'POST' && url.pathname === '/ack') {
      if (!authorized(request, env)) return new Response('unauthorized', { status: 401 });
      let ids = [];
      try {
        ids = (await request.json()).ids || [];
      } catch {
        return new Response('bad json', { status: 400 });
      }
      for (const id of ids) await env.LINE_QUEUE.delete(`evt:${id}`);
      return new Response('ok');
    }

    return new Response('not found', { status: 404 });
  },
};

function authorized(request, env) {
  return (request.headers.get('authorization') || '') === `Bearer ${env.POLL_KEY}`;
}

async function verifySignature(body, signature, secret) {
  if (!signature || !secret) return false;
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const mac = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(body));
  const expected = btoa(String.fromCharCode(...new Uint8Array(mac)));
  if (expected.length !== signature.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) {
    diff |= expected.charCodeAt(i) ^ signature.charCodeAt(i);
  }
  return diff === 0;
}
