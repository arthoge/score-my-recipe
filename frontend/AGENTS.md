# Agent Guide — Score my recipe frontend

---

## Projects instructions

Ensure you read the [global AGENTS.md](../AGENTS.md),
those file add specific instruction for the frontend part.

## Bootstrap

Run these commands in order every time you start work in a fresh environment:

```bash
cd frontend  # if you start from the project folder
cp .env.example .env
pnpm install --frozen-lockfile
```

## NVM and pnpm specific

if you see a "local-nvm.sh" file in the `frontend` folder,
source it: `cd frontend; . ./local-nvm.sh` before using `pnpm commands`

---

## Key Commands

| Command          | Purpose                                         | Approx. time       |
| ---------------- | ----------------------------------------------- | ------------------ |
| `pnpm dev`       | Start dev server at <http://localhost:5173>     | ~3s (runs forever) |
| `pnpm build`     | Production build                                | ~20s               |
| `pnpm check`     | TypeScript + Svelte type check                  | ~10s               |
| `pnpm lint`      | Prettier + ESLint                               | ~15s               |
| `pnpm format`    | Auto-format all files                           | ~5s                |
| `pnpm i18ncheck` | check translation files                         | ~5s                |
| `pnpm i18nsync`  | add missing translations in secondary languages | ~5s                |

> External API calls to OpenFoodFacts will fail in sandboxed environments — this is expected. Focus on UI and code correctness.

---

## Pre-PR Validation (mandatory)

Before opening any pull request, run all of the following and fix every error:

```bash
pnpm format
pnpm lint
pnpm check
pnpm test
pnpm build
```

No PR should be opened with lint errors, type errors, or build failures.

---

## Source Structure

```text
src/
├── routes/           # SvelteKit pages and API endpoints
├── lib/
│   ├── api/          # External API integration (OFF, Folksonomy, Prices, Search)
│   ├── ui/           # Reusable Svelte components and forms
│   ├── i18n/         # svelte-i18n messages and setup
│   └── stores/       # Svelte stores for state management
├── params/           # SvelteKit parameter matchers
└── app.html          # HTML shell
```

## Coding style

Always add a meaningful doc string to functions, modules, etc.

Add comments for complex part or to justify non intuitive choices, or to summarize long code chunks (so that reader can quickly get an overview of the code). Still try not to be too verbose (find the right balance). If you use advance features (that not many programers might now), add a link to the documentation in the comment.

When you comment, put line breaks at points that make sense for understanding (to optimize next git diff if comment is amended).

Try to make the code as clear as possible, by normalizing cases before processing, using the single responsibility pattern.

We try to use the frameworks at their best to have easy to read, semantic code.

---

### UI & Design

- **Read [DESIGN.md](../docs/DESIGN.md) before writing any UI code.** It defines the component patterns, colour tokens, button hierarchy, and responsive conventions.
- Always use DaisyUI semantic tokens (`bg-primary`, `text-base-content`) — never hardcode hex values.
- Follow the button priority hierarchy defined in DESIGN.md.

### Internationalisation

- **All user-facing strings must go through svelte-i18n.**
- Always provide a `default` fallback: `$_('some.key', { default: 'Fallback text' })`.
- Add new keys to `src/lib/i18n/messages/en-US.json` first.

---

## Common Issues

| Problem                             | Cause                            | Fix                                                  |
| ----------------------------------- | -------------------------------- | ---------------------------------------------------- |
| `Internal Error` or fetch failures  | External APIs blocked in sandbox | Expected — ignore for UI work                        |
| Build fails after dependency change | Stale lockfile                   | `rm -rf node_modules pnpm-lock.yaml && pnpm install` |
| App won't start                     | Missing `.env`                   | `cp .env.example .env`                               |
| CI fails on lint/format             | Unformatted code                 | `pnpm format && pnpm lint`                           |

---

## What This Project Does Not Have

- **Limited test coverage.** The project has a test runner (Vitest) but few tests currently exist. Always run `pnpm test` before opening a PR to ensure consistency with CI. Supplement automated tests with manual validation: run the dev server and verify that navigation, search UI, and settings page work without console errors.
