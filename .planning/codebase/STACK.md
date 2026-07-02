# Technology Stack

**Analysis Date:** 2026-02-27

## Languages

**Primary:**
- Python 3.11+ - Core simulator, ML training, backend API, coaching logic
- TypeScript/React 18.2.0 - Frontend UI and visualization
- Rust - High-performance combat engine (PyO3 extension)
- JavaScript - Data scraper for meta information

**Secondary:**
- Cython - Performance optimization for combat calculations and feature engineering

## Runtime

**Environment:**
- Python 3.11+ (target version per `ruff.toml`)
- Node.js 20+ (frontend, see workflow)
- Rust 1.93.0+ (combat engine compilation via Maturin)

**Package Manager:**
- pip - Python packages
- npm - JavaScript/Node dependencies
- cargo - Rust dependencies

**Lockfiles:**
- `package-lock.json` - Frontend and scraper dependencies pinned
- `requirements*.txt` - Python dependencies pinned by major.minor version

## Frameworks

**Backend:**
- FastAPI 0.100.0+ - REST API server (`app/api/server.py`)
- Uvicorn 0.23.0+ - ASGI server for FastAPI
- Pydantic 2.5.0+ - Data validation and schema definition

**Frontend:**
- React 18.2.0 - UI component framework
- Vite 7.3.1+ - Build tool and dev server
- Tailwind CSS 4.1.18+ - Utility-first styling

**ML:**
- PyTorch 2.1.0+ - Deep learning framework (optional, device: CPU/CUDA/MPS)
- XGBoost 2.0.0+ - Gradient boosting for placement model
- LightGBM 4.0.0+ - Alternative gradient boosting
- scikit-learn 1.3.0+ - ML utilities and cross-validation
- PyArrow 14.0+ - Parquet I/O and Arrow arrays (critical for batch data)

**Simulator:**
- NumPy 1.24.0+ - Numerical computations
- Pandas 2.1.0+ - Data manipulation
- Rayon (Rust) - Parallel batch processing in combat engine
- Parquet (Rust) - Direct Parquet writes from Rust engine

**Testing:**
- pytest 7.4.3+ - Unit/integration test runner
- pytest-timeout - Test timeout enforcement
- Cython 3.0.11 - Build extension modules

**Development/CLI:**
- Watchdog 3.0.0+ - File system monitoring for log watching
- python-dotenv 1.0.0+ - Environment variable loading
- PyYAML 6.0.1+ - YAML config parsing
- Rich 13.0.0+ - Rich terminal output
- tqdm 4.66.0+ - Progress bars

**Logging & Visualization:**
- TensorBoard 2.15.0+ - Training metrics visualization
- Matplotlib 3.8.0+ - Plot generation
- Seaborn 0.13.0+ - Statistical visualization

**Data & Math:**
- scipy 1.11.0+ - Information theory and numerical methods
- scikit-image 0.21.0 - Image processing (legacy)

## Key Dependencies

**Critical:**
- `pyarrow 14.0+` - Parquet serialization (training data), Arrow arrays for batch processing. No PyArrow = data I/O bottleneck and test fallbacks to JSON.
- `torch 2.1.0+` - GPU acceleration (optional but strongly recommended for training). Falls back to CPU if unavailable.
- `xgboost 2.0.0+` - Placement prediction model. Uses external memory mode for large datasets (Gate B+).

**Infrastructure:**
- `pydantic 2.5.0+` - Request/response validation for API
- `fastapi 0.100.0+` - REST endpoints for model serving
- `uvicorn 0.23.0+` - ASGI server
- `aiosqlite 0.19.0+` - Local SQLite support (reserved for future history tracking)
- `requests 2.32.0+` - HTTP requests to external APIs

**Performance Optimization:**
- `rayon 1.10` (Rust) - Parallel batch processing in combat engine
- `serde / serde_json` (Rust) - Fast JSON serialization for Rust engine
- Cython extensions: `combat_fast` (hex distance, damage calcs), `fe_fast` (feature engineering)
- Rust PyO3 extension: `tft_combat_engine` (full combat simulation)

**Legacy/Optional:**
- `ray 2.10.0` - Distributed RL training (legacy, in `simulator/Simulator/` quarantine)
- `jax ~0.4.13`, `flax ~0.7.2`, `chex ~0.1.7` - JAX neural nets (legacy, quarantine)
- `gymnasium ~0.29.1` - RL environment API (legacy)
- `PettingZoo 1.24.3` - Multi-agent RL (legacy)
- `dm-tree` - Tree operations (legacy)
- `tabulate` - Terminal tables (legacy)

## Configuration

**Environment:**
- `.env` file support via `python-dotenv`
- Key env vars: `COACH_OUTPUTS_DIR`, `COACH_CHECKPOINT_DIR`, `COACH_ARTIFACT_ROOT`, `AWS_REGION`, `S3_BUCKET`, `S3_PREFIX`, `REPO_URL`, `REPO_REF`
- Config modules: `config.py` (root shim), `app/config.py` (app-specific), `simulator/config.py` (simulator env loading)

**Build:**
- `ruff.toml` - Linting (E, F, W, I rules) and formatting (double quotes, 100 char line length)
- `pytest.ini` - Test discovery paths and exclusions
- `.pre-commit-config.yaml` - Ruff lint/format, secret detection, AGENTS/CLAUDE sync
- `Cargo.toml` - Rust combat engine with PyO3, serde, rayon, arrow, parquet

**CI/CD:**
- GitHub Actions workflows in `.github/workflows/`:
  - `test-coverage.yml` - Full test suite, parity gates, coach eval gates
  - `lint.yml` - Code quality checks
  - `secret-scan.yml` - Secret detection
  - `deploy.yml` - Deployment pipeline
  - `auto-resolve-conflicts.yml` - Conflict resolution

## Platform Requirements

**Development:**
- Python 3.11+ interpreter
- Node.js 20+ with npm
- Rust 1.93.0+ toolchain (for combat engine builds)
- C compiler (for Cython extensions)
- Windows (local log watching uses MetaTFT Overwolf paths) or Linux (CI/cloud)

**Production:**
- Python 3.11+ runtime with PyArrow, torch (optional), XGBoost
- Node.js 20+ for frontend build/serve
- Linux (AWS EC2: c8g.48xlarge CPU or g5.2xlarge GPU)
- Optional: CUDA 11.8+ if GPU training enabled

**Deployment Target:**
- AWS EC2: c8g.48xlarge (Graviton ARM64, 192 vCPUs) for CPU simulation
- AWS EC2: g5.2xlarge or g6.2xlarge (x86_64, 1 GPU) for GPU training
- Docker/container support via bootstrap scripts

## Build Artifacts

**Python Extensions:**
- `simulator/core/combat_fast/` - Cython module (Windows build via `setup.py build_ext`)
- `models/fe_fast/` - Cython module (feature engineering acceleration)
- `simulator/core/rust_engine/target/wheels/*.whl` - PyO3 extension (via Maturin)

**Output Formats:**
- Parquet (primary) - Training data chunks, simulator outputs
- JSON (fallback) - When PyArrow unavailable
- JSONL - Game traces, coach evaluation logs
- CSV - Meta snapshots, augment tables

---

*Stack analysis: 2026-02-27*
