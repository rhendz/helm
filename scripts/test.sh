#!/usr/bin/env bash
set -euo pipefail

# M002: EmailAgent and StudyAgent are present but non-truth; exclude their tests from CI
# These tests exist for reference but should not block workflow-engine core verification
uv run --frozen --extra dev pytest \
  --ignore=tests/unit/test_email_deep_seed_queue.py \
  --ignore=tests/unit/test_email_followup_worker.py \
  --ignore=tests/unit/test_email_followup.py \
  --ignore=tests/unit/test_email_ingest_service.py \
  --ignore=tests/unit/test_email_operator.py \
  --ignore=tests/unit/test_email_reconciliation_sweep_worker.py \
  --ignore=tests/unit/test_email_scaffolds.py \
  --ignore=tests/unit/test_email_seed.py \
  --ignore=tests/unit/test_email_send_recovery_worker.py \
  --ignore=tests/unit/test_email_send_recovery.py \
  --ignore=tests/unit/test_email_service.py \
  --ignore=tests/unit/test_email_thread_state.py \
  --ignore=tests/unit/test_email_triage_worker.py \
  --ignore=tests/unit/test_study_agent_handlers.py \
  --ignore=tests/unit/test_study_agent_mvp.py \
  --ignore=tests/unit/test_study_agent.py \
  --ignore=tests/unit/test_study_ingest_repository.py \
  --ignore=tests/integration/test_study_ingest_route.py
