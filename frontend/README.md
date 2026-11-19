# Online Cinema — frontend

React 19 + TypeScript + Vite. SPA that talks to the FastAPI backend through `/api`.

## Run

```bash
npm ci
npm run dev        # http://localhost:3000, /api is proxied to localhost:8000
```

Or the whole stack: `docker compose up -d` from the repository root (service `frontend`).

## Scripts

| Script                 | What it does                                                      |
| ---------------------- | ----------------------------------------------------------------- |
| `npm run lint`         | ESLint (typed rules)                                              |
| `npm run format`       | Prettier: format all files                                        |
| `npm run format:check` | Prettier: check only (CI)                                         |
| `npm run build`        | `tsc -b` type check + production build to `dist/`                 |
| `npm run gen:api`      | Regenerate `src/api/schema.d.ts` from the running backend OpenAPI |

## Structure

```
src/
├── api/          # fetch wrapper (client.ts), endpoints by domain, generated types
├── auth/         # AuthProvider: access token in memory, refresh cookie on reload
├── hooks/        # useLibrary (favorites / purchased / cart ids), useCatalogParams
├── components/   # Navbar, MovieCard, MovieCatalog, Comments, moderator/ ...
├── pages/        # one file per route (see router.tsx)
└── utils/        # formatting, error text, form helpers
```
