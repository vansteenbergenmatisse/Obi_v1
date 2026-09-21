# Rollback Notes

If a deploy goes bad:

1. Run `make rollback ENV=production`.
2. Confirm error rate drops below 2%.
3. Page the on-call rotation.
4. Open an incident ticket and record the timeline.
