"""
Backward-compatibility wrapper for app.engine.injector.
Redirects to app.core.injector.
"""
from app.core.injector import TextInjector, send_paste_event

__all__ = ["TextInjector", "send_paste_event"]
