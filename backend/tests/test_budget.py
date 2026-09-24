import threading

from app.budget import DAY_SECONDS, RequestBudget


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_the_limit_then_refuses():
    budget = RequestBudget(3, clock=FakeClock())
    assert [budget.try_spend() for _ in range(5)] == [True, True, True, False, False]
    assert budget.remaining() == 0


def test_requests_free_up_after_the_rolling_window():
    clock = FakeClock()
    budget = RequestBudget(2, clock=clock)
    budget.try_spend()
    clock.now += 60
    budget.try_spend()
    assert not budget.try_spend()

    clock.now += DAY_SECONDS - 60  # the first request is now a day old
    assert budget.remaining() == 1
    assert budget.try_spend()
    assert not budget.try_spend()


def test_never_overspends_under_concurrency():
    budget = RequestBudget(50)
    granted = []

    def spend():
        for _ in range(20):
            if budget.try_spend():
                granted.append(1)

    threads = [threading.Thread(target=spend) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(granted) == 50
