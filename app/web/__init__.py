"""
Friday Web Studio package.
"""


def start_server(*args, **kwargs):
    from app.web.server import start_server as _start
    return _start(*args, **kwargs)


__all__ = ["start_server"]
