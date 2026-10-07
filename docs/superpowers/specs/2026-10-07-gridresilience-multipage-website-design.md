# GridResilience Multipage Website Design

**Date:** 2026-10-07  
**Status:** Approved and implemented; interactive browser QA pending

## Objective

Restructure GridResilience from a single dense dashboard into a premium, organized website with a true landing page and one focused operational capability per route. Preserve all simulation state, API calls, request payloads, response handling, topology behavior, benchmark data flow, scientific calculations, and numerical results.

The approved visual direction is light-first, editorial, and utility-oriented: warm neutral surfaces, deep navy typography, restrained blue/cyan/green accents, generous whitespace, original power-grid imagery, and a persistent dark-theme option. It must avoid the dense neon styling and repetitive card treatment associated with generic AI dashboards.

## Information Architecture

The application will use client-side routing with these distinct URLs:

| Route | Primary purpose | Existing capability rendered |
| --- | --- | --- |
| `/` | Explain the project and direct visitors into the platform | New landing-page presentation using live benchmark findings |
| `/operations` | Configure and run one incident scenario | Scenario presets, `ControlBar`, and six `MetricsOverview` cards |
| `/topology` | Inspect the IEEE-14 network state | `TopologyGraph` with existing selection behavior |
| `/prediction` | Review downstream line-failure forecasts | `FailurePredictionPanel` with all 15 lines |
| `/mitigation` | Review preventive controller behavior | `MitigationPanel` and PPO action trace |
| `/recovery` | Review post-cascade restoration | `RecoveryPanel` and restoration actions |
| `/timeline` | Inspect incident progression | `CascadeTimeline` |
| `/benchmarks` | Review validated research evidence | `ComparisonPanel`, complete benchmark table, and Phase 6 audit |

Unknown frontend paths redirect to `/`. Browser back/forward navigation and direct page links must work. A page refresh must preserve the selected route, although in-memory simulation results may reset exactly as they do today after a full application reload.

## Landing Page

The homepage contains no simulation controls or detailed operational panels. It introduces the project with:

1. A full website header with the GridResilience identity, primary navigation, backend-health status, theme control, and a clear “Launch Operations” action.
2. A premium hero with the approved message direction: “Predict instability. Protect the grid.” It includes a concise description, Operations and Methodology calls to action, and an original locally stored power-grid/control-room image.
3. The three validated findings from `/benchmarks`: `+4.17 pp` customer load served, `69.5%` less load shed, and `−3.0 pp` total blackout rate. Neutral placeholders render until the API responds; the UI must not hard-code a successful loading state.
4. Three capability explanations for forecasting, mitigation, and safety-constrained recovery.
5. A compact six-stage workflow that links into the corresponding feature routes.
6. A restrained project footer with platform and IEEE-14 context.

Marketing copy must accurately describe implemented behavior and must not introduce unsupported claims. Imagery is decorative and must have useful alternative text. Production must use a locally stored original asset rather than hotlinking the temporary mockup photograph.

## Shared Navigation and Page Structure

Desktop uses a sticky top navigation rather than the current dashboard-only icon rail. The primary links are Home, Operations, Topology, Prediction, Mitigation, and Recovery. Timeline and Benchmarks appear in a clearly labeled Research menu. All eight destinations appear directly in the mobile menu.

Every feature route uses the same header, footer, content width, theme, and page-introduction pattern. The page introduction names the active phase and briefly explains what the user can inspect there. The main content region then contains one dominant existing feature panel at a comfortable full-page width.

Scenario presets move from the global header to the Operations page so the landing and research pages remain uncluttered. The existing `handleSelectPreset` function and preset values remain unchanged.

## Controller and Data Flow

`App.jsx` remains the sole controller for:

- backend health, grid, benchmark, scenario-input, progress, result, and selected-element state;
- `/health`, `/grid`, `/benchmarks`, and `/simulate` calls;
- request payload construction;
- preset selection and simulation execution handlers;
- response use and the props passed to scientific/operational panels.

The router changes which presentation page receives those props. Navigating between routes does not remount the controller, refetch data, or discard the active simulation result.

Page components are presentational. They may compose existing panels and page headings, but they do not fetch data, calculate topology, transform scientific output, or own simulation behavior. Theme preference is UI-only state and may live in a dedicated theme provider.

## Routing and Static Hosting

Use the current stable `react-router-dom` release compatible with React 19 and `BrowserRouter` for standard URLs. Route metadata lives in one manifest used by the shared navigation and route tests.

Vite development continues to proxy the current API endpoints. Unified FastAPI production mode receives an SPA static-file fallback only for frontend paths that were not matched by existing API routes. The `/health`, `/grid`, `/simulate`, `/results/{run_id}`, and `/benchmarks` contracts and behavior remain unchanged.

The frontend deployment configuration includes explicit rewrites for the seven non-root page routes to `index.html`, leaving API paths untouched.

## Theme System

The default visual theme is light. A header control switches between light and dark modes and stores the choice under a namespaced local-storage key. The saved preference applies before the main interface paints to avoid a visible theme flash.

Both themes use the same semantic CSS variables for background, surface, text, border, status, and action colors. Every existing operational component must consume those tokens and remain readable in both themes. Status colors retain their operational meaning:

- green for safe or successful states;
- amber for degraded or caution states;
- red for dangerous or failed states;
- blue/cyan for informational and active states;
- purple only for model/research context.

Keyboard focus, contrast, reduced-motion handling, mobile navigation, tables, topology labels, chart lines, badges, inputs, and disabled states must work in both themes.

## Component Structure

Create focused presentation units:

- `pages/HomePage.jsx`
- `pages/OperationsPage.jsx`
- `pages/TopologyPage.jsx`
- `pages/PredictionPage.jsx`
- `pages/MitigationPage.jsx`
- `pages/RecoveryPage.jsx`
- `pages/TimelinePage.jsx`
- `pages/BenchmarksPage.jsx`
- `components/site/SiteHeader.jsx`
- `components/site/SiteFooter.jsx`
- `components/site/PageIntro.jsx`
- `components/site/LandingHero.jsx`
- `components/site/ThemeProvider.jsx`
- `routes/siteRoutes.js`

Refactor `AppShell` around the shared website header/footer. Remove the obsolete icon sidebar and compact operations hero after their responsibilities move to routed pages and the landing-page presentation.

Existing scientific panels remain separate and receive the same source values they receive today.

## Empty, Loading, and Error States

- The homepage benchmark strip shows neutral em-dash placeholders until `/benchmarks` returns.
- Operational pages render existing neutral pre-run states when `simResult` is absent.
- Recovery must not claim `STABLE` before a result exists.
- Benchmark audit success appears only when Phase 6 recovery rows exist.
- Existing fetch warnings, simulation error reporting, progress text, and button disabling behavior remain unchanged.
- The active navigation state derives from the current route, never from scroll position.

## Responsive Behavior

At desktop widths, the header exposes the main navigation and the landing hero uses a balanced text-and-image composition. At tablet widths, the hero stacks and dense research tables retain horizontal scrolling. At mobile widths, navigation moves into an accessible menu, landing content becomes single-column, calls to action remain visible, and every functional panel uses the full viewport width without clipped values or controls.

## Validation

Implementation is complete when:

1. Every route renders its single assigned major capability.
2. Navigation, active states, direct loading, browser back/forward, and unknown-path redirection work.
3. One simulation can be started on Operations and its unchanged result can be viewed across all feature pages without rerunning.
4. All 15 prediction rows, complete mitigation/recovery traces, timeline events, benchmark rows, and audit content remain available.
5. Light and dark themes persist and introduce no clipped or unreadable UI.
6. Frontend route/theme tests, lint, and production build pass.
7. Existing Python tests pass with no scientific or backend-contract regressions.
8. Live `/health`, `/grid`, `/benchmarks`, and `/simulate` behavior remains unchanged.
9. Browser console inspection reports no application errors during navigation, theme switching, and one full simulation flow when browser access is available.

## Out of Scope

- Authentication, user accounts, or saved user profiles
- Persisting simulation results across a full browser reload
- Changes to models, physics, simulation algorithms, API schemas, payloads, or benchmark values
- New operational features unrelated to page organization, theming, and landing-page presentation
