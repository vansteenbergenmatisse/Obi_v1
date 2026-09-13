"""Scheduler registration (``app.main._build_scheduler``).

The three baseline jobs (daily lightweight cron, complete-reconcile interval, worker tick) are
always registered. The optional DEV fast lightweight-reconcile poll — which lets a live page edit
self-propagate in ~N seconds instead of waiting for the daily cron — is off by default and only
registers an *additional* interval job when ``dev_reconcile_interval_seconds`` is set. The
scheduler is inspected without being started, so no ``shutdown`` is needed.
"""

from __future__ import annotations

from apscheduler.triggers.interval import IntervalTrigger

from app.main import _build_scheduler

_BASELINE_JOB_IDS = {"lightweight_reconcile", "complete_reconcile", "worker_tick"}
_DEV_JOB_ID = "dev_lightweight_reconcile"


def test_dev_reconcile_job_absent_by_default(gateway, settings):
    # dev_reconcile_interval_seconds unset -> no extra job, baseline intact. Set explicitly to None
    # rather than trusting the fixture default: an operator's ambient .env may export
    # DEV_RECONCILE_INTERVAL_SECONDS (the local auto-propagate run-config), which pydantic would
    # otherwise leak into this hermetic case.
    settings = settings.model_copy(update={"dev_reconcile_interval_seconds": None})
    scheduler = _build_scheduler(gateway, settings)
    job_ids = {j.id for j in scheduler.get_jobs()}
    assert _DEV_JOB_ID not in job_ids
    assert job_ids >= _BASELINE_JOB_IDS


def test_dev_reconcile_job_registered_when_interval_set(gateway, settings):
    dev_settings = settings.model_copy(update={"dev_reconcile_interval_seconds": 30})
    scheduler = _build_scheduler(gateway, dev_settings)

    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert _DEV_JOB_ID in jobs
    assert set(jobs) >= _BASELINE_JOB_IDS  # in addition to, not instead of, the baseline

    dev_job = jobs[_DEV_JOB_ID]
    assert isinstance(dev_job.trigger, IntervalTrigger)
    assert dev_job.trigger.interval.total_seconds() == 30
