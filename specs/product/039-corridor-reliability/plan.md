# 039 Corridor Reliability — Plan

1. Add a log line in `app/comfort.py::_overpass_features` naming the endpoint
   and the exception/status per attempt.
2. Widen the endpoint list (primary + the configured mirror + a second public
   mirror) and raise the outer HTTP timeout (default 90 s) while keeping the QL
   `[timeout:40]` so the server-side query gives up first.
3. Unit-test the retry (first endpoint fails → mirror used) and the timeout
   path with mocked `requests`.

Risks: a longer timeout delays the route response on a down endpoint; keep the
"data gap, never a 5xx" fallback so the worst case is slow-but-graceful.
