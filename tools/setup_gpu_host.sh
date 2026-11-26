#!/usr/bin/env bash
set -euo pipefail

# Host GPU/ROCm verification & setup helper for `meddah serve` + Docker Ollama profiles.
CHECK_ONLY=0
if [[ "${1:-}" == "--check-rocm" ]]; then
  CHECK_ONLY=1
fi

echo "== Meddah Host GPU & Container Pre-Flight Check =="

if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[OK] NVIDIA driver detected:"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
  echo "Recommended Docker Compose profile: --profile ollama-nvidia"
  exit 0
fi

if [[ -e /dev/dri ]]; then
  echo "[INFO] /dev/dri present:"
  ls -l /dev/dri || true
else
  echo "[WARN] /dev/dri not found (no GPU render nodes exposed)."
fi

if [[ -e /dev/kfd ]]; then
  echo "[OK] /dev/kfd present for AMD ROCm compute."
  if id -nG "$USER" | grep -qw "video" && id -nG "$USER" | grep -qw "render"; then
    echo "[OK] User '$USER' belongs to both 'video' and 'render' groups."
  else
    echo "[WARN] Add user '$USER' to video and render groups:"
    echo "  sudo usermod -aG video,render $USER"
  fi
  echo "Recommended Docker Compose profile: --profile ollama-amd"
else
  echo "[INFO] /dev/kfd not present. If using Intel/AMD Vulkan fallback, use --profile ollama-vulkan;"
  echo "       otherwise run headless Zero-AI Tier A (default) or --profile ollama-cpu."
  if [[ "$CHECK_ONLY" -eq 0 ]]; then
    echo "For AMD ROCm hosts on Ubuntu/Debian, ensure amdgpu-dkms / rocm kernel drivers are installed"
    echo "and run: sudo usermod -aG video,render $USER"
  fi
fi
