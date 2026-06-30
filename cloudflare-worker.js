// Cloudflare Worker — IPRoyal relay
//
// Why: Anthropic's Claude Code sandbox blocks outbound to proxy gateways at
// both DNS and IP layers, so I can't reach geo.iproyal.com from there. But
// I can reach *.workers.dev:443 freely. This Worker is the bridge: I send
// `GET https://landrelay.<you>.workers.dev/?url=<encoded target>` from the
// sandbox; the Worker opens a TCP socket to IPRoyal, sends an HTTP CONNECT
// to tunnel to the target, upgrades to TLS, fires the GET, and streams the
// response back to me.
//
// Setup: paste this whole file into a Cloudflare Worker, add secret
// IPROYAL_PROXY = http://USER:PASS@geo.iproyal.com:12321, deploy.

import { connect } from 'cloudflare:sockets';

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const target = url.searchParams.get('url');

    // Health check at the root with no params
    if (!target) {
      return new Response(
        'IPRoyal relay live. Usage: GET /?url=<urlencoded https://target>',
        { status: 200, headers: { 'Content-Type': 'text/plain' } }
      );
    }
    if (!env.IPROYAL_PROXY) {
      return new Response('IPROYAL_PROXY secret not configured', { status: 500 });
    }

    // Parse the IPRoyal credentials out of the secret
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

    try {
      // 1. TCP socket to IPRoyal (secureTransport=starttls so we can upgrade
      //    to TLS after the CONNECT handshake)
      const socket = connect(
        { hostname: proxyHost, port: parseInt(proxyPort) },
        { secureTransport: "starttls", allowHalfOpen: false }
      );

      // 2. HTTP CONNECT to tunnel to the target
      const auth = btoa(`${user}:${pass}`);
      const connectReq =
        `CONNECT ${targetHost}:${targetPort} HTTP/1.1\r\n` +
        `Host: ${targetHost}:${targetPort}\r\n` +
        `Proxy-Authorization: Basic ${auth}\r\n` +
        `User-Agent: ${UA}\r\n` +
        `Proxy-Connection: Keep-Alive\r\n\r\n`;

      const w0 = socket.writable.getWriter();
      await w0.write(new TextEncoder().encode(connectReq));
      w0.releaseLock();

      // 3. Read CONNECT response — expect HTTP/1.1 200
      const r0 = socket.readable.getReader();
      const { value: hsValue } = await r0.read();
      r0.releaseLock();
      const hs = new TextDecoder().decode(hsValue);
      if (!hs.startsWith('HTTP/1.1 200') && !hs.startsWith('HTTP/1.0 200')) {
        return new Response(
          `CONNECT failed: ${hs.slice(0, 400)}`,
          { status: 502 }
        );
      }

      // 4. Upgrade to TLS for HTTPS targets
      const finalSocket = isHttps
        ? socket.startTls({ servername: targetHost })
        : socket;

      // 5. Send the actual GET through the (TLS) tunnel
      const path = (t.pathname || '/') + (t.search || '');
      const httpReq =
        `GET ${path} HTTP/1.1\r\n` +
        `Host: ${targetHost}\r\n` +
        `User-Agent: ${UA}\r\n` +
        `Accept: */*\r\n` +
        `Accept-Language: en-US,en;q=0.9\r\n` +
        `Accept-Encoding: identity\r\n` +
        `Connection: close\r\n\r\n`;

      const w1 = finalSocket.writable.getWriter();
      await w1.write(new TextEncoder().encode(httpReq));
      w1.releaseLock();

      // 6. Read response fully
      const r1 = finalSocket.readable.getReader();
      const chunks = [];
      while (true) {
        const { value, done } = await r1.read();
        if (done) break;
        if (value) chunks.push(value);
      }
      r1.releaseLock();

      const totalLen = chunks.reduce((a, c) => a + c.length, 0);
      const fullResp = new Uint8Array(totalLen);
      let off = 0;
      for (const c of chunks) {
        fullResp.set(c, off);
        off += c.length;
      }

      // 7. Split HTTP headers from body
      const respText = new TextDecoder('utf-8', { fatal: false }).decode(fullResp);
      const headerEnd = respText.indexOf('\r\n\r\n');
      if (headerEnd < 0) {
        return new Response('No header terminator in response', { status: 502 });
      }
      const headerBlock = respText.slice(0, headerEnd);
      const body = fullResp.slice(headerEnd + 4);
      const status = parseInt(respText.match(/^HTTP\/1\.\d (\d+)/)?.[1] || '200');
      const contentType =
        headerBlock.match(/content-type:\s*([^\r\n]+)/i)?.[1]
        || 'text/html; charset=utf-8';

      // Pass through the response. We strip Set-Cookie / Transfer-Encoding etc.
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
      return new Response(`Relay error: ${e.message || e}`, { status: 500 });
    }
  }
};
