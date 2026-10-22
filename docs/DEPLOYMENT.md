# Deploy GridResilience

The React dashboard runs on Vercel; the Python API and saved models run on Render.

## Render API

Create a Python web service from `https://github.com/GaneshKotakonda/grid`, branch
`main`, with the repository root as its root directory. `render.yaml` records the
equivalent Blueprint configuration. The runtime requirements exclude development
tests, and PyTorch is installed from its CPU wheel index before the other packages.

- Build: `pip install --no-cache-dir 'torch>=2.2,<3' --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r requirements-render.txt`
- Start: `python -m uvicorn src.api:app --host 0.0.0.0 --port $PORT --workers 1`
- Health check: `/health`
- Python: `3.12.12`
- Environment: `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`, `MPLBACKEND=Agg`.

Keep one worker: models and simulation results live in process memory. Saved
checkpoints and the predictive dataset are already tracked under `outputs/` and
must be included in the checkout. No training step is required to serve the API.
Results disappear when the process restarts. Free Render instances sleep when
idle; a first request may take longer while the service starts.

## Vercel frontend

Import the same repository into Vercel with:

- Root directory: `frontend`
- Framework: Vite
- Node.js: `22.x`
- Install: `npm ci`
- Build: `npm run build`
- Output: `dist`

Set `VITE_API_BASE_URL` to the actual Render service HTTPS URL, without an endpoint
path, for Production and Preview. Redeploy after changing the value because Vite
embeds it into the browser build. This address is public configuration, not a
secret. The existing FastAPI CORS middleware accepts the dashboard's requests.

`frontend/vercel.json` keeps direct navigation to every dashboard page working.
The dashboard fetches benchmark JSON from Render while `/benchmarks` on Vercel
remains the research page.

Leave `VITE_API_BASE_URL` unset for local Vite development (the dev proxy forwards
requests to port 8000) or the unified FastAPI server. `frontend/.env.example`
documents the setting.

## Release checks

After deploying, open `/operations` on the Vercel URL and confirm **API online**.
Run a scenario and inspect the topology and prediction pages. The API's `/health`,
`/grid`, and `/benchmarks` endpoints should return JSON. A completed simulation's
grid outcome, including a blackout, is distinct from a hosting failure.
