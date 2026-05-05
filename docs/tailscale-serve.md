# Tailscale Serve — Digest API

Expose the local Digest API server over your private tailnet using `tailscale serve`.

## Prerequisites

- Digest API running: `bin/digest-serve.sh`
- Tailscale connected: `tailscale status`

## Expose the API

```bash
tailscale serve --bg 8787
```

This proxies `https://<machine>.tailnet-name.ts.net` → `http://127.0.0.1:8787`. The `--bg` flag runs it as a background daemon that survives shell exits.

## Verify

```bash
tailscale serve status
```

Expected output includes a line like:
```
https://<machine>.tailnet-name.ts.net
|-- / proxy http://127.0.0.1:8787
```

Test from another device on the tailnet:
```bash
curl https://<machine>.tailnet-name.ts.net/health
```

## Remove

```bash
tailscale serve --bg --remove 8787
```

Verify it's gone:
```bash
tailscale serve status
```
