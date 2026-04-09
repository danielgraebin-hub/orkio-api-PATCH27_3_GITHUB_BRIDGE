import time


class RealtimeDuplicationGuard:

    def __init__(self):
        self.last_commit_ts = {}
        self.window_ms = 1200

    def should_commit(self, session_id: str) -> bool:
        now = int(time.time() * 1000)

        last = self.last_commit_ts.get(session_id)

        if last and (now - last) < self.window_ms:
            return False

        self.last_commit_ts[session_id] = now
        return True


guard = RealtimeDuplicationGuard()
