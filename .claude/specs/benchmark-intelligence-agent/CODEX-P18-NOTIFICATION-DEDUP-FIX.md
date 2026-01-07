# CODEX-P18: Notification Deduplication Bug Fixes

## Overview

Fix 4 bugs causing repeated notifications of the same benchmarks on consecutive days.

## Bug Analysis

### Bug 1: Relative DB Path Creates Empty Database Per Run

**File**: `src/storage/notification_history.py`

**Problem**: `NOTIFICATION_HISTORY_DB = "notification_history.db"` uses a relative path. When the cron job or container runs from a different working directory, a new empty database is created. `should_notify()` always returns `True` because the new DB has no records.

**Fix**: Use an absolute path based on the project root.

```python
# Before (line 20)
NOTIFICATION_HISTORY_DB = "notification_history.db"

# After
import os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOTIFICATION_HISTORY_DB = os.path.join(_PROJECT_ROOT, "notification_history.db")
```

---

### Bug 2: Notification History Updated Only After All Sends Complete

**File**: `src/notifier/feishu_notifier.py`

**Problem**: `batch_increment()` is called at line 119, after ALL notifications are sent (lines 89-106). If any `_send_webhook` call fails mid-batch, already-sent notifications are NOT recorded. Next run will re-notify the same items.

**Fix**: Record each notification immediately after successful send, not in a batch at the end.

**Changes required**:

1. In `notify()` method, track successfully sent candidates:
   - After each successful `send_card()` call, immediately record that URL
   - After successful `_send_medium_priority_summary()`, immediately record those URLs
   - Remove the batch `batch_increment()` call at the end

2. Add helper method to record single notification:
```python
def _record_notified(self, candidate: ScoredCandidate) -> None:
    """Record a single notification immediately after successful send."""
    if candidate.url:
        self.notification_history.increment_notify_count(candidate.url, candidate.title)
```

3. Modify the notification loop (around lines 89-98):
```python
# 1. Push high priority cards
for candidate in high_priority:
    try:
        await self.send_card("...", candidate)
        self._record_notified(candidate)  # Record immediately after success
    except Exception as e:
        logger.warning("Failed to send card for %s: %s", candidate.title, e)
    await asyncio.sleep(constants.FEISHU_RATE_LIMIT_DELAY)

# 2. Push medium priority summary
if medium_priority:
    try:
        await self._send_medium_priority_summary(...)
        # Record all medium priority after successful summary send
        for c in medium_priority:
            self._record_notified(c)
    except Exception as e:
        logger.warning("Failed to send medium priority summary: %s", e)
```

4. Remove lines 114-120 (the batch update at the end).

---

### Bug 3: SQLite Fallback Returns All Candidates, Bypassing Dedup

**File**: `src/storage/storage_manager.py`

**Problem**: When Feishu save fails and falls back to SQLite (lines 57-64), it returns `candidates` (the full input list) instead of an empty list. The caller (`main.py`) then calls `notifier.notify(actually_saved)` with ALL candidates, causing duplicate notifications.

**Fix**: SQLite fallback should return an empty list OR a clearly marked fallback list that main.py handles differently.

**Option A (Recommended)**: Return empty list, skip notifications on fallback
```python
# Lines 57-64: Change return candidates to return []
await self.sqlite.save(candidates)
logger.info("SQLite backup saved: %d items", len(candidates))
return []  # Don't notify on fallback - will sync and notify later
```

**Option B**: Add flag to distinguish fallback scenario (more complex, not recommended for this fix)

---

### Bug 4: Source Field Normalization Mismatch

**File**: `src/storage/feishu_storage.py` (read) + `src/main.py` (compare)

**Problem**:
- Feishu stores source as list/enum: `['GitHub']` or `GitHub`
- `main.py` uses `c.source` which is lowercase: `github`
- `recent_urls_by_source` lookup fails due to case mismatch

**Location in main.py** (lines 194-207):
```python
source_value = record.get("source", "default")
...
recent_urls_by_source.setdefault(source_value, set()).add(url_key)
```

Then at lines 212-216:
```python
window_days = constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE.get(
    c.source, ...  # c.source is "github" (lowercase)
)
recent_urls = recent_urls_by_source.get(c.source, set())  # Won't find "GitHub"
```

**Fix**: Normalize source field to lowercase in both read and compare.

In `src/storage/feishu_storage.py`, `read_existing_records()` method (around line 720):
```python
source_value = fields.get(source_field, "default")
# Normalize source to lowercase string
if isinstance(source_value, list):
    source_value = source_value[0] if source_value else "default"
source_value = str(source_value).lower()
record_item: dict[str, Any] = {
    ...
    "source": source_value,
}
```

---

## Implementation Order

1. Bug 1 (DB path) - Critical, immediate fix
2. Bug 4 (source normalization) - Critical for window dedup
3. Bug 3 (SQLite fallback) - Prevents cascade failure
4. Bug 2 (incremental recording) - Resilience improvement

## Testing

### Manual Test Scenarios

1. **DB Path Test**:
   - Run `python -m src.main` from project root
   - Run `cd /tmp && python /path/to/src/main.py`
   - Verify both use the same `notification_history.db`

2. **Source Normalization Test**:
   - Check Feishu records with source = `['GitHub']`
   - Verify `read_existing_records()` returns `source: "github"`
   - Verify `recent_urls_by_source["github"]` matches

3. **Incremental Recording Test**:
   - Mock `_send_webhook` to fail on 2nd card
   - Verify 1st card is recorded in notification_history.db
   - Run again, verify 1st card is NOT re-notified

4. **SQLite Fallback Test**:
   - Mock Feishu API to fail
   - Verify no notifications sent (or only send after sync succeeds)

## Acceptance Criteria

- [ ] Same benchmark NOT notified on consecutive days
- [ ] notification_history.db persists across runs from any cwd
- [ ] Source field dedup window works for GitHub, arXiv, etc.
- [ ] Partial webhook failure doesn't cause full re-notification
- [ ] SQLite fallback doesn't trigger notifications

## Files Changed

- `src/storage/notification_history.py` - Absolute path
- `src/notifier/feishu_notifier.py` - Incremental recording
- `src/storage/storage_manager.py` - SQLite fallback return
- `src/storage/feishu_storage.py` - Source normalization
