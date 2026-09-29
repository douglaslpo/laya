#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Runs the repository guardrails (see docs/guardrails.md). Stdlib-only Python.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/guardrails_check.py "$@"
