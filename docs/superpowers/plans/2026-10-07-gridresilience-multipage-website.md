# GridResilience Multipage Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dense GridResilience dashboard into a polished multi-page website with a true project homepage, focused operational routes, and persistent light/dark themes.

**Architecture:** Keep `App.jsx` mounted once as the owner of all backend and simulation state. Add BrowserRouter routes whose page components receive existing state and callbacks, a shared site shell, a route manifest for navigation/page introductions, and a UI-only theme provider. Add SPA document fallback for known frontend paths in FastAPI production and the frontend static-hosting configuration while retaining existing API route behavior.

**Tech Stack:** React 19, Vite 8, React Router DOM 7.18.4, existing FastAPI/Starlette static serving, CSS custom properties, generated local hero image.

**Spec:** `docs/superpowers/specs/2026-10-07-gridresilience-multipage-website-design.md`

## Global Constraints

- `App.jsx` remains the sole controller for backend health, grid data, benchmark data, scenario input, progress, results, selected topology elements, API calls, payloads, and handlers.
- Preserve the current `/health`, `/grid`, `/benchmarks`, and `/simulate` requests, payload fields, response usage, numerical values, topology calculations, and model behavior exactly.
- Keep `TopologyGraph`, `FailurePredictionPanel`, `MitigationPanel`, `RecoveryPanel`, `CascadeTimeline`, `ComparisonPanel`, and `MetricsOverview` as presentation components with their current data inputs.
- Keep the three homepage findings sourced from `/benchmarks` and show neutral placeholders until that response arrives.
- Keep all eight routes, browser history behavior, direct links, and unknown-path redirect behavior from the approved spec.
- Default to the approved light theme; persist a user-selected dark theme in local storage without a startup flash.
- Store the generated landing image in `frontend/public`; do not hotlink external imagery at runtime.
- Add no API endpoints, API payload fields, scientific logic, or model dependencies.

## Review Focus

- Client route changes must not remount the state-owning `App` or discard simulation results.
- Direct feature URLs must render both under Vite and the FastAPI static host while existing API routes keep precedence.
- Theme initialization must handle missing, invalid, and valid local-storage values without throwing or flashing the wrong theme.
- Empty simulation and benchmark data must keep honest neutral states across every route.
- Narrow screens must keep navigation usable and long values, forecast rows, tables, and topology controls readable in both themes.

---

## File Structure

- Create `frontend/src/routes/siteRoutes.js` as the shared route and navigation metadata manifest.
- Create `frontend/src/pages/HomePage.jsx`, `OperationsPage.jsx`, `TopologyPage.jsx`, `PredictionPage.jsx`, `MitigationPage.jsx`, `RecoveryPage.jsx`, `TimelinePage.jsx`, and `BenchmarksPage.jsx` as prop-driven view composition only.
- Create `frontend/src/components/site/SiteHeader.jsx`, `SiteFooter.jsx`, `PageIntro.jsx`, `LandingHero.jsx`, and `ThemeProvider.jsx` for shared website presentation.
- Refactor `frontend/src/App.jsx`, `frontend/src/main.jsx`, `frontend/src/components/ui/AppShell.jsx`, `frontend/src/components/Navbar.jsx`, `frontend/src/components/ui/Sidebar.jsx`, `frontend/src/components/ui/OperationalHero.jsx`, `frontend/src/index.css`, and `frontend/index.html` to connect the site shell, routes, metadata, and theme.
- Create `frontend/public/gridresilience-hero.png` as a locally stored original visual asset.
- Modify `frontend/package.json` and its lockfile for React Router DOM.
- Create `frontend/vercel.json` for direct frontend-route rewrites.
- Modify `src/api.py` to add a known-path SPA fallback after existing API routes.
- Update `README.md` route and frontend structure notes.

## Task 1: Add Route Metadata, Router, and Page Components

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/main.jsx`, `frontend/src/App.jsx`
- Create: `frontend/src/routes/siteRoutes.js`
- Create: `frontend/src/pages/OperationsPage.jsx`, `TopologyPage.jsx`, `PredictionPage.jsx`, `MitigationPage.jsx`, `RecoveryPage.jsx`, `TimelinePage.jsx`, `BenchmarksPage.jsx`

**Interfaces:**
- `SITE_ROUTES`: ordered records `{ path, label, group, title, description }`, one record per approved route.
- Each operational page accepts only existing panel props. `OperationsPage` composes `ControlBar` and `MetricsOverview`; remaining pages compose one existing main panel.
- `App.jsx` remains mounted above `<Routes>` and passes the existing state and callbacks down; unmatched paths use `<Navigate to="/" replace />`.

- [x] Install React Router DOM at the pinned compatible 7.18.4 version.
- [x] Add the route manifest with exact paths and labels from the spec.
- [x] Create the seven functional page compositions; no page may fetch, transform, or recalculate API data.
- [x] Wrap `App` with `BrowserRouter` in `main.jsx` and render the page selected by route inside `App`.
- [x] Move scenario controls and six metric cards to `/operations`; assign topology, prediction, mitigation, recovery, timeline, and benchmark panels to their routes.
- [x] Confirm the `App` function owns all existing hooks once and that no router layout remounts it during navigation.
- [ ] Run `npm run lint` and `npm run build`; inspect all routes in the running Vite app and use browser back/forward plus direct URL loading.

## Task 2: Build the Shared Website Shell and Accessible Navigation

**Files:**
- Create: `frontend/src/components/site/SiteHeader.jsx`, `SiteFooter.jsx`, `PageIntro.jsx`
- Modify: `frontend/src/components/ui/AppShell.jsx`, `frontend/src/components/Navbar.jsx`, `frontend/src/components/ui/Sidebar.jsx`, `frontend/src/App.jsx`, `frontend/src/index.css`

**Interfaces:**
- `AppShell({ children })` renders one shared header, page content, and footer around the route view.
- `SiteHeader({ isBackendHealthy })` reads `SITE_ROUTES` for links; Operations controls are rendered on the Operations page, not in the global header.
- `PageIntro({ title, description, phase })` provides a consistent heading block for functional pages.

- [x] Replace the icon-only sidebar with a sticky desktop top navigation, active-route indication, grouped Research navigation for Timeline and Benchmarks, and a keyboard-accessible mobile menu exposing all eight destinations.
- [x] Add consistent feature-page introductions and the shared restrained footer.
- [x] Preserve the backend health indicator in the shared header.
- [x] Remove the old scroll-observer navigation and dashboard-only shell once all route views use the shared shell.
- [ ] Run frontend lint/build and manually inspect active links, keyboard operation, mobile menu, and feature-page headings.

## Task 3: Implement the Landing Page and Local Hero Image

**Files:**
- Create: `frontend/src/pages/HomePage.jsx`, `frontend/src/components/site/LandingHero.jsx`, `frontend/public/gridresilience-hero.png`
- Modify: `frontend/src/App.jsx`, `frontend/src/index.css`, `frontend/index.html`

**Interfaces:**
- `HomePage({ benchmarkData })` renders the landing page and obtains every finding from the existing benchmark response.
- `LandingHero` accepts the Operations and methodology link targets; it owns no API or simulation state.

- [x] Generate an original premium power-grid/control-room photograph-style asset and save it locally under `frontend/public`.
- [x] Implement the approved hero copy, image, concise project description, and Operations/Methodology calls to action.
- [x] Render the three `/benchmarks` findings, showing em-dash placeholders until fields arrive.
- [x] Add three capability summaries, the six-step site workflow linked to routes, and a compact footer treatment.
- [x] Set landing-page metadata/title and descriptive image alternative text.
- [ ] Run frontend lint/build and inspect image loading, initial loading placeholders, and responsive landing-page layout.

## Task 4: Add Persistent Light/Dark Theme Across Every Route

**Files:**
- Create: `frontend/src/components/site/ThemeProvider.jsx`
- Modify: `frontend/src/main.jsx`, `frontend/index.html`, `frontend/src/components/site/SiteHeader.jsx`, `frontend/src/index.css`, and existing visual components where hard-coded colors block theme support.

**Interfaces:**
- Theme context exposes `{ theme, toggleTheme }` only; it owns no project or simulation data.
- Storage key: `gridresilience-theme`; valid values are `light` and `dark`; default is `light`.

- [x] Add an early theme bootstrap in `index.html` that validates the stored theme and applies the light default before the app paints.
- [x] Implement `ThemeProvider` and a keyboard-accessible header toggle with an accessible label reflecting the next action.
- [x] Define light and dark semantic tokens in `index.css` and update hard-coded visual state colors in forecast bars, topology, tables, forms, badges, and panel treatments to use theme-aware tokens where appropriate while preserving status meanings.
- [x] Retain reduced-motion rules and visible keyboard focus in both themes.
- [ ] Run frontend lint/build and manually inspect initial theme, toggling, refresh persistence, missing/invalid stored values, and all route content in both themes.

## Task 5: Support Direct URLs in Production Static Hosting

**Files:**
- Modify: `src/api.py`
- Create: `frontend/vercel.json`

**Interfaces:**
- The FastAPI static fallback returns `index.html` only for the seven whitelisted non-root frontend page paths when no real file exists.
- Existing API route registration remains before the SPA fallback and static mount; unknown API and frontend paths retain 404 behavior.
- Vercel rewrites only `/operations`, `/topology`, `/prediction`, `/mitigation`, `/recovery`, `/timeline`, and `/benchmarks` to `/index.html`.

- [x] Add a scoped StaticFiles subclass or equivalent fallback that serves the SPA shell for only approved frontend paths.
- [x] Preserve existing API route order and methods, and ensure `/results/{run_id}` still resolves before static handling.
- [x] Add explicit Vercel rewrite rules for each approved non-root route, with no rewrite of API paths.
- [x] Build the frontend and verify direct requests to all seven paths serve `index.html`, API paths still serve API responses, and unknown paths still return 404.

## Task 6: Finish Responsive Styling, Documentation, and End-to-End Review

**Files:**
- Modify: `frontend/src/index.css`, `README.md`, and any of the page/site files above required by visual review.

- [x] Tune tablet and mobile breakpoints for the shared nav, landing page, each operational panel, and benchmark table in both themes.
- [x] Update README with the eight routes and explain that simulation state is shared during in-app navigation and resets on a full reload.
- [x] Run `npm run lint` and `npm run build`.
- [x] Run `python3 -m pytest` and confirm all existing API and scientific tests pass; restore any generated output-only diffs caused by tests before finalizing.
- [ ] With the browser, visit every route directly, navigate back and forward, switch themes, run one simulation, inspect its result across the feature routes, and confirm the console has no application errors.
- [x] Inspect the final diff to confirm no simulation algorithm, request payload, benchmark result, topology calculation, or API response contract changed.

## Plan Self-Review

- **Spec coverage:** Routes and controller flow are Task 1; navigation and shared page patterns are Task 2; landing content and locally stored image are Task 3; theme and accessibility are Task 4; production direct URLs and API precedence are Task 5; responsive behavior, documentation, and overall verification are Task 6.
- **Step clarity:** Each checkbox is one implementation or verification action with named files and observable behavior.
- **Interface consistency:** All page props originate in the unchanged `App` controller. `SITE_ROUTES` is the single navigation metadata source. `ThemeProvider` exposes only display preference.
- **Review focus coverage:** Route state, direct URLs/API precedence, preference storage, empty data, and responsive content all have a named manual verification step in the owning task.
- **Proportion:** The six tasks track the coupled routing, shell, landing, theme, hosting, and final presentation units from the approved spec.

## Implementation Verification

Implemented in the active checkout. Twelve frontend tests pass, including retained scenario state, exact simulation payload, all feature-route entries, all 15 forecasts, unknown-client-path redirect, scroll reset, and persistent theme preference with blocked storage. Frontend lint and production build pass. All 100 Python tests pass, including the original 97 scientific/API tests and three website routing checks. The `App.jsx` controller body is byte-for-byte identical to the original.

Interactive browser checks remain unchecked because saved browser permissions block localhost access. All eight Vite page routes were verified over HTTP, including HTML/JSON negotiation for `/benchmarks`. A final read-only review found no critical issues; its cache-header, document-scroll, and mobile-menu findings were addressed.

## Final Review and Decisions

The independent review found no critical issues. Its three important findings were fixed: `Vary: Accept` for shared HTML/JSON URLs, document scroll reset on navigation, and a scrollable viewport-capped mobile menu. The routing-header and scroll regression tests were observed failing before their fixes and passing afterward. Live production HTTP checks covered all eight pages, the three read APIs, and a simulation returning all 15 forecasts.

- Work remained in the accepted active checkout; the tradeoff is visible changes on main rather than worktree isolation.
- `/benchmarks` uses Accept-based HTML/JSON negotiation to retain the approved page URL and API contract; incorrect negotiation would expose JSON to page visitors.
- Interactive browser QA remains pending because localhost browser access was denied; visual, keyboard, history, and browser-console behavior are not claimed verified.
- Hosted Vercel behavior remains unverified because deployment was not requested; the supplied configuration still needs hosted verification when deployed.
- Cloud-file hydration was resolved and the complete scientific suite passed; test-generated output changes were restored.
- The hero is an original built-in imagegen asset at `frontend/public/gridresilience-hero.png`. Prompt: realistic editorial photograph of high-voltage transmission towers and a modern substation at dusk, warm sunset and navy steel, distant hills, restrained wide composition, no text/logos/watermarks/UI.
- Deferred minor: reformat compressed JSX into ordinary multiline formatting.
