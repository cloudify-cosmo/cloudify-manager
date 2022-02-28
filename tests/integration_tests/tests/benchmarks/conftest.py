import pytest
from datetime import datetime


def log_result(name, timing, start, stop):
    if timing:
        name = f'{name}.{timing}'
    print(f'BENCH {name}: {stop - start}')


class _Timings(object):
    def __init__(self, func_name):
        self.records = {}
        self._func_name = func_name

    def start(self, name=None):
        self.records[name] = [datetime.utcnow(), None]

    def stop(self, name=None):
        if name not in self.records:
            raise RuntimeError(f'bench called stop without a start: {name}')
        self.records[name][1] = datetime.utcnow()
        log_result(self._func_name, name, *self.records[name])


@pytest.fixture()
def bench(request):
    """Give the tests a "bench" fixture for measuring time.

    Tests can call `self.bench.start()` and `self.bench.stop()` (with an
    optional name). Results will be printed out immediately, and also at the
    end of the session (using the pytest_sessionx hooks).
    """
    func_name = request.function.__name__
    storage = request.session.stash['benchstorage']
    timings = _Timings(func_name)
    request.cls.bench = timings
    storage[func_name] = timings


def pytest_sessionstart(session):
    session.stash['benchstorage'] = {}


def pytest_sessionfinish(session, exitstatus):
    print('\nBENCHMARK RESULTS')
    for name, timings in session.stash['benchstorage'].items():
        for timing, (start, stop) in timings.records.items():
            log_result(name, timing, start, stop)
