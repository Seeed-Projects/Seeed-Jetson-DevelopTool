#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <app_name> [cv|genai|robotics|general]"
  exit 1
fi

APP_NAME="$1"
TEMPLATE="${2:-general}"
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)/projects/${APP_NAME}"

if [[ -e "$BASE_DIR" ]]; then
  echo "[ERROR] App already exists: $BASE_DIR"
  exit 2
fi

mkdir -p "$BASE_DIR"/{src,scripts,configs,tests,artifacts}

cat > "$BASE_DIR/README.md" <<DOC
# ${APP_NAME}

Template: ${TEMPLATE}

## Dev Checklist
- Confirm JetPack/L4T compatibility
- Validate CUDA/TensorRT runtime
- Validate camera/sensor I/O if needed
- Add minimal reproducible pipeline first

## Run
\`\`\`bash
./scripts/run.sh
\`\`\`
DOC

cat > "$BASE_DIR/scripts/run.sh" <<'DOC'
#!/usr/bin/env bash
set -euo pipefail
echo "Run your app entrypoint here"
DOC
chmod +x "$BASE_DIR/scripts/run.sh"

echo "[OK] Created app workspace: $BASE_DIR"
