# GridResilience Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the existing live GridResilience dashboard as a premium power-grid operations console without changing its behavior or scientific data flow.

**Architecture:** Keep `App.jsx` as the sole controller and preserve every existing prop and data calculation. Add reusable presentation primitives, reorganize layout through those primitives, and move visual rules into a responsive CSS system.

**Tech Stack:** React 19, Vite 8, Lucide React, CSS, FastAPI-backed JSON endpoints.

**Spec:** `docs/superpowers/specs/2026-10-06-gridresilience-frontend-redesign-design.md`

## Global Constraints

- Do not modify backend Python files, API contracts, request payloads, response usage, models, simulation logic, topology calculations, saved data, or numerical results.
- Do not introduce mock data, fake routes, hardcoded simulation output, or new research claims.
- Preserve all six KPIs, all 15 line predictions, presets, control meanings, timeline data, recovery actions, benchmark rows, and the Phase 6 audit.
- Keep the operational hero between 140 and 180 px on desktop and source its findings only from `/benchmarks`.
- Use anchor navigation only.

## Review Focus

- Benchmark data may be unavailable during initial render: show neutral placeholders without fallback claims in the hero.
- Simulation results may represent total blackout or empty recovery actions: preserve zero values and clear empty states.
- Prediction lists must contain and display all 15 entries, including a separately identified initiating outage.
- Narrow viewports must keep every control and table usable without overlapping the sidebar or header.
- Existing SVG selection, overlay toggles, labels, and detail drawer must continue working after presentation changes.

---

### Task 1: Shared Presentation Primitives and App Shell

**Files:**
- Create: `frontend/src/components/ui/AppShell.jsx`
- Create: `frontend/src/components/ui/Sidebar.jsx`
- Create: `frontend/src/components/ui/OperationalHero.jsx`
- Create: `frontend/src/components/ui/PanelHeader.jsx`
- Create: `frontend/src/components/ui/StatusBadge.jsx`
- Create: `frontend/src/components/ui/MetricCard.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: existing React children, `benchmarkData`, backend health state, and anchor IDs.
- Produces: presentation-only components with no data fetching, mutation, or domain calculations.

- [ ] Implement the reusable components with semantic class names and accessible labels.
- [ ] Add the navy design tokens, shared panels, badges, typography, scrollbars, and responsive shell CSS.
- [ ] Run `npm run lint` and resolve presentation-component errors.

### Task 2: Compose the Approved Page Hierarchy

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Navbar.jsx`
- Modify: `frontend/src/components/ControlBar.jsx`

**Interfaces:**
- Consumes: the Task 1 presentation components and all existing `App.jsx` state and handlers.
- Produces: the approved shell, compact hero, command deck, anchors, and unchanged control behavior.

- [ ] Wrap the existing page with `AppShell`, preserving state declarations, effects, handlers, fetch calls, and child props.
- [ ] Restyle the sticky header while preserving the exact three preset payloads and backend health indicator.
- [ ] Restyle the command deck while preserving field values, setters, disabled state, and simulation handler.
- [ ] Verify the hero and command deck fit the initial desktop viewport at a typical 1440×900 viewport.
- [ ] Run `npm run lint` and `npm run build`.

### Task 3: Live Operations Workspace

**Files:**
- Modify: `frontend/src/components/MetricsOverview.jsx`
- Modify: `frontend/src/components/TopologyGraph.jsx`
- Modify: `frontend/src/components/FailurePredictionPanel.jsx`
- Modify: `frontend/src/components/MitigationPanel.jsx`
- Modify: `frontend/src/components/RecoveryPanel.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: unchanged props from `App.jsx` and the Task 1 UI primitives.
- Produces: six aligned KPI cards and a responsive 65/35 operations workspace without domain-logic changes.

- [ ] Convert the six KPI presentations to `MetricCard` while retaining all current calculations.
- [ ] Restyle the topology canvas, legend, toggles, line states, selection drawer, and labels without changing graph calculations.
- [ ] Restyle the risk list and retain all predictions, sorting, categories, outage-trigger distinction, and scroll behavior.
- [ ] Restyle mitigation and recovery output while retaining complete actual action lists and calculations.
- [ ] Run `npm run lint` and `npm run build`.

### Task 4: Timeline and Research Evidence

**Files:**
- Modify: `frontend/src/components/CascadeTimeline.jsx`
- Modify: `frontend/src/components/ComparisonPanel.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: unchanged audit-log and benchmark response structures.
- Produces: compact incident progression, complete benchmark table, validated findings, and Phase 6 audit.

- [ ] Restyle the timeline into a responsive horizontal sequence while retaining audit-log derivations.
- [ ] Restyle the benchmark findings, full table, best-controller emphasis, and recovery audit without changing values.
- [ ] Run `npm run lint` and `npm run build`.

### Task 5: End-to-End Verification

**Files:**
- Modify only files required to resolve verified presentation defects.

**Interfaces:**
- Consumes: the complete frontend and the existing FastAPI application.
- Produces: a verified responsive dashboard with no console errors or contract regressions.

- [ ] Run `npm install`, `npm run lint`, and `npm run build` in `frontend/`.
- [ ] Run `python3 -m pytest` from the repository root.
- [ ] Start the FastAPI and Vite servers and verify `/health`, `/grid`, `/benchmarks`, and one `/simulate` flow.
- [ ] Verify Moderate, Stressed, Severe, and custom control behavior in the browser.
- [ ] Verify topology updates, all 15 predictions, mitigation, timeline, recovery, benchmarks, and Phase 6 audit.
- [ ] Verify desktop and mobile layouts and inspect browser console logs.
- [ ] Review `git diff` to confirm no backend or saved-result files changed.

