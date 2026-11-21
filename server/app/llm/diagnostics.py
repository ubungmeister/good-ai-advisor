"""Bounded, content-free error diagnostics shared by provider and validator stages."""

def status_code(exc):
    for value in (getattr(exc, "status_code", None), getattr(exc, "code", None),
                  getattr(getattr(exc, "response", None), "status_code", None)):
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
            return value
    return None


def log_failure(logger, stage, exc, attempt=None):
    # No exception text, repr, traceback, request objects, prompts or generated content.
    logger.warning("AI stage failed: stage=%s error_type=%s status=%s attempt=%s",
                   stage, type(exc).__name__, status_code(exc), attempt,
                   extra={"ai_failure": True, "stage": stage, "error_type": type(exc).__name__,
                          "status_code": status_code(exc), "attempt": attempt})
