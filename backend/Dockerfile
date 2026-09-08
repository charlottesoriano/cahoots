# ---- Base image ----
    FROM python:3.14-slim

    # ---- Bring in uv ----
    # uv ships as a single static binary. Instead of pip-installing it, copy it
    # straight out of Astral's official image. Fast, no extra layers.
    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
    
    # ---- Build-time env ----
    ENV UV_COMPILE_BYTECODE=1 \
        UV_LINK_MODE=copy \
        PYTHONUNBUFFERED=1
    
    # UV_COMPILE_BYTECODE  — precompile .pyc on install, slightly faster startup
    # UV_LINK_MODE=copy    — copy packages into .venv instead of hardlinking
    #                        (hardlinks can fail across Docker's layer filesystem)
    # PYTHONUNBUFFERED      — don't buffer stdout/stderr, so logs show up live
    
    # ---- Working directory ----
    WORKDIR /app
    
    # ---- Dependencies (cached layer) ----
    # Copy ONLY the dependency manifests first. Docker caches each instruction as a
    # layer; as long as these two files don't change, the slow `uv sync` below is
    # reused from cache even when your source code changes.
    COPY pyproject.toml uv.lock ./
    RUN uv sync --frozen --no-dev
    
    # --frozen   — install exactly what's in uv.lock, error if lock is stale
    # --no-dev   — skip the [dependency-groups] dev deps (pytest, httpx)
    
    # ---- Application code ----
    COPY . .
    
    # ---- Network ----
    EXPOSE 8000
    # Documentation only — tells readers/tools the app listens on 8000.
    # Actual port mapping happens in docker-compose.yml.
    
    # ---- Startup command ----
    CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
    # --host 0.0.0.0  — listen on all interfaces. Default 127.0.0.1 is only
    #                   reachable from inside the container; 0.0.0.0 lets Docker
    #                   forward host traffic in.
    # no --reload     — that's a dev-only feature; compose adds it back for local use.
    