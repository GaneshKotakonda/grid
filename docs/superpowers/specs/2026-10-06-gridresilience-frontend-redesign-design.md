# GridResilience Frontend Redesign Design

## Goal

Redesign the existing GridResilience React dashboard to match the visual language and information hierarchy of the supplied interactive prototype while preserving every existing API contract, simulation control, model-derived value, topology calculation, benchmark result, and scientific behavior.

## Functional Boundary

`frontend/src/App.jsx` remains the sole controller for backend health, grid data, benchmark data, scenario inputs, simulation execution, progress text, results, and selected topology elements. Existing `fetch` calls, request payloads, response usage, handlers, state variables, preset values, and component data contracts remain unchanged.

No Python file, FastAPI endpoint, model checkpoint, saved result, benchmark CSV, inference path, cascade calculation, PPO action, recovery calculation, or topology calculation will be modified. No mock data or fabricated simulation output will be introduced.

## Presentation Architecture

The redesign introduces focused presentation components:

- `AppShell`: fixed navigation rail, sticky header, responsive content frame, and footer.
- `Sidebar`: anchor-only navigation for operations, prediction, mitigation, recovery, and benchmarks.
- `OperationalHero`: compact 140–180 px introduction and three validated findings sourced only from `/benchmarks`, with neutral placeholders while data loads.
- `PanelHeader`: consistent panel titles, descriptions, icons, and optional status badges.
- `StatusBadge`: shared semantic status treatment.
- `MetricCard`: shared structure for the six live result KPIs.

Existing domain panels retain their props and calculations. Presentation markup and CSS may be reorganized, but behavior stays within the existing component boundaries.

## Page Hierarchy

The desktop page contains:

1. A 72–80 px left navigation rail.
2. A compact sticky header with the product identity, preset controls, model pills, and live FastAPI connection state.
3. A compact operational hero and validated-impact block totaling 140–180 px.
4. The Scenario Command Deck immediately beneath the hero and within the initial desktop viewport.
5. Six equal-height KPI cards: System Risk, Failed Lines, Load Served, System State, Load Shed, and Load Restored.
6. A 65/35 operations workspace with the interactive IEEE-14 topology on the left and the full prediction, mitigation, and recovery panels on the right.
7. The incident progression timeline.
8. The complete Phase 5.5 benchmark comparison and Phase 6 recovery audit.

The sidebar scrolls to page anchors. It adds no routes, pages, or alternate data flows.

## Visual System

The interface uses a restrained operations-console palette: deep navy page layers, slightly raised blue-gray panels, low-contrast blue borders, near-white primary text, muted blue-gray secondary text, cyan for controls and prediction, green for safe/recovered states, amber for warnings and load shed, red for failures, and purple for predictive-model metadata.

Panels use 10–16 px radii, consistent 4/8/12/16/24/32 px spacing, tabular numerical values, compact 10–16 px interface type, and 24–30 px KPI values. Depth comes from subtle gradients and borders rather than heavy glow.

## Domain Panels

The topology remains the existing SVG implementation with all 14 buses, 15 lines, five transformer connections, overlays, labels, click selection, detail drawer, and line-state calculations. Its canvas and legend receive presentation styling only.

The prediction panel continues to render all 15 line predictions sorted by probability. The initiating outage remains separately labeled as the outage trigger and is not presented as a GCN prediction.

The mitigation panel continues to render the actual PPO audit events, actions, rewards, and load-shed values. The recovery panel continues to render actual reconnected lines and committed actions. Long lists become internally scrollable.

The timeline continues deriving stages from the audit log. The benchmark panel continues consuming `/benchmarks` and preserves the complete controller table, validated findings, and Phase 6 invariant audit values.

## Responsive Behavior

At widths below roughly 1200 px, the topology becomes full width and the intelligence panels move below it. The sidebar becomes a compact horizontal/mobile navigation surface. Controls and presets wrap without changing their meaning. KPI cards move from six columns to three, two, and one as space narrows. Tables remain horizontally scrollable, and all interactive controls remain reachable.

## Loading, Error, and Empty States

The live backend indicator continues reflecting `/health`. The hero uses neutral placeholders until `/benchmarks` resolves. The command deck keeps the existing disabled/loading behavior and existing progress string. Empty result panels use neutral operational messages and do not invent values. Existing request error handling remains unchanged.

## Verification

Verification covers `npm run lint`, `npm run build`, the existing Python test suite because the frontend consumes API contracts, and manual browser checks at desktop and mobile widths. Browser checks cover presets, custom controls, one complete simulation, topology interaction and overlays, all 15 predictions, PPO and recovery output, the timeline, benchmark data, Phase 6 audit, and console errors.

