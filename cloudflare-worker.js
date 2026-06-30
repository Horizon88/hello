// IPRoyal relay via Cloudflare Worker — robust version.
// Reads the CONNECT response stream until \r\n\r\n exactly, then upgrades
// to TLS. Earlier version did a single read() that fragmented some servers.

import { connect } from 'cloudflare:sockets';

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15';
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: false });

function findTerminator(buf, term) {
  outer: for (let i = 0; i <= buf.length - term.length; i++) {
    for (let j = 0; j < term.length; j++) {
      if (buf[i + j] !== term[j]) continue outer;
    }
    return i;
  }
  return -1;
}

async function readUntilTerminator(reader, term) {
  let buf = new Uint8Array(0);
  while (true) {
    const { value, done } = await reader.read();
    if (done) return null;
    const next = new Uint8Array(buf.length + value.length);
    next.set(buf);
    next.set(value, buf.length);
    buf = next;
    const idx = findTerminator(buf, term);
    if (idx >= 0) return buf.slice(0, idx + term.length);
  }
}

async function readAll(reader) {
  const chunks = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    if (value && value.length) chunks.push(value);
  }
  const totalLen = chunks.reduce((a, c) => a + c.length, 0);
  const buf = new Uint8Array(totalLen);
  let off = 0;
  for (const c of chunks) { buf.set(c, off); off += c.length; }
  return buf;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const target = url.searchParams.get('url');

    if (!target) {
      return new Response(
        'IPRoyal relay live. Usage: GET /?url=<urlencoded target>',
        { status: 200, headers: { 'Content-Type': 'text/plain' } }
      );
    }
    if (!env.IPROYAL_PROXY) {
      return new Response('IPROYAL_PROXY secret not configured', { status: 500 });
    }

    const m = env.IPROYAL_PROXY.match(/^https?:\/\/([^:]+):([^@]+)@([^:]+):(\d+)/);
    if (!m) {
      return new Response(
        'IPROYAL_PROXY must be http://USER:PASS@HOST:PORT',
        { status: 500 }
      );
    }
    const [, user, pass, proxyHost, proxyPort] = m;

    let t;
    try { t = new URL(target); }
    catch { return new Response('Malformed target URL', { status: 400 }); }

    const targetHost = t.hostname;
    const isHttps = t.protocol === 'https:';
    const targetPort = t.port || (isHttps ? '443' : '80');
    const term = encoder.encode('\r\n\r\n');

    try {
      // 1. TCP socket to IPRoyal — must be starttls so we can upgrade later
      const socket = connect(
        { hostname: proxyHost, port: parseInt(proxyPort) },
        { secureTransport: 'starttls' }
      );

      // 2. Send CONNECT with Basic auth
      const auth = btoa(`${user}:${pass}`);
      const connectReq = encoder.encode(
        `CONNECT ${targetHost}:${targetPort} HTTP/1.1\r\n` +
        `Host: ${targetHost}:${targetPort}\r\n` +
        `Proxy-Authorization: Basic ${auth}\r\n` +
        `User-Agent: ${UA}\r\n` +
        `Proxy-Connection: Keep-Alive\r\n\r\n`
      );
      const writer = socket.writable.getWriter();
      await writer.write(connectReq);
      writer.releaseLock();

      // 3. Read CONNECT response (loop until \r\n\r\n — may arrive in chunks)
      const reader = socket.readable.getReader();
      const hsBuf = await readUntilTerminator(reader, term);
      reader.releaseLock();

      if (!hsBuf) {
        return new Response('Proxy closed connection before CONNECT response', { status: 502 });
      }
      const hs = decoder.decode(hsBuf);
      if (!/^HTTP\/1\.[01]\s+2\d\d/.test(hs)) {
        return new Response(`CONNECT rejected: ${hs.slice(0, 400)}`, { status: 502 });
      }

      // 4. Upgrade socket. For HTTP targets skip the TLS handshake.
      const finalSocket = isHttps
        ? socket.startTls({ servername: targetHost })
        : socket;

      // 5. Send the HTTP request through the (TLS) tunnel
      const path = (t.pathname || '/') + (t.search || '');
      const httpReq = encoder.encode(
        `GET ${path} HTTP/1.1\r\n` +
        `Host: ${targetHost}\r\n` +
        `User-Agent: ${UA}\r\n` +
        `Accept: text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8\r\n` +
        `Accept-Language: en-US,en;q=0.9\r\n` +
        `Accept-Encoding: identity\r\n` +
        `Connection: close\r\n\r\n`
      );
      const w2 = finalSocket.writable.getWriter();
      await w2.write(httpReq);
      w2.releaseLock();

      // 6. Read full response
      const r2 = finalSocket.readable.getReader();
      const full = await readAll(r2);
      r2.releaseLock();

      const fullText = decoder.decode(full);
      const headerEnd = fullText.indexOf('\r\n\r\n');
      if (headerEnd < 0) {
        return new Response('No header terminator in upstream response', { status: 502 });
      }
      const status = parseInt(fullText.match(/^HTTP\/1\.\d (\d+)/)?.[1] || '200');
      const headerBlock = fullText.slice(0, headerEnd);
      const contentType =
        headerBlock.match(/content-type:\s*([^\r\n]+)/i)?.[1] ||
        'text/html; charset=utf-8';
      const body = full.slice(headerEnd + 4);

      return new Response(body, {
        status,
        headers: {
          'Content-Type': contentType,
          'X-Relay-Target': targetHost,
          'X-Relay-Bytes': String(body.length),
          'Cache-Control': 'no-store',
        },
      });
    } catch (e) {
      return new Response(
        `Relay error: ${e.message || e}\n${(e.stack || '').slice(0, 800)}`,
        { status: 500 }
      );
    }
  },
};
