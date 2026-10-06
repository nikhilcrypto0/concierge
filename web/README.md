# Concierge demo UI

A Next.js app with two screens: the Tidewell customer site with the chat assistant (`/`), and the support console where a person approves refunds (`/console`, behind a password). The project overview, design decisions, and results are in the [root README](../README.md).

The app never touches the database. It calls the Concierge API through its own `/api` routes, which attach the API keys on the server, so no key ever reaches the browser.

## Run it

```bash
npm install
cp .env.example .env.local   # then fill in the values below
npm run dev                  # http://localhost:3000
```

| Setting | What it is |
|---|---|
| `CONCIERGE_API_URL` | Where the API runs, for example `http://127.0.0.1:8000` |
| `CONCIERGE_CLIENT_KEY` | The key after `webapp:` in the API's `CLIENT_API_KEYS` |
| `CONCIERGE_OPERATOR_KEY` | The key after `support-lead:` in the API's `OPERATOR_API_KEYS` |
| `CONSOLE_PASSWORD` | Password for `/console`, 16 or more characters |
| `CONSOLE_SESSION_SECRET` | Random secret that signs the login cookie, 32 or more characters |

If either console setting is missing or too short, the console and every approval route stay locked.

## Checks

```bash
npm run lint
npx next typegen && npx tsc --noEmit
npm run build
```

This version of Next.js has breaking changes from older releases. Read the guides in `node_modules/next/dist/docs/` before changing routing or server code (see `AGENTS.md`).
