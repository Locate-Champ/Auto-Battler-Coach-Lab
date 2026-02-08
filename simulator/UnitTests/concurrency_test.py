import config
from Concurrency.data_worker import DataWorker


def _make_worker_without_init():
    # DataWorker is a Ray actor class; use the modified class directly so we
    # can unit-test pure helper methods without spinning up Ray.
    worker_cls = DataWorker.__ray_metadata__.modified_class
    return worker_cls.__new__(worker_cls)


def get_step_actions_parallel_test():
    worker = _make_worker_without_init()
    original_mode = config.SINGLE_PLAYER
    config.SINGLE_PLAYER = False
    try:
        terminated = {"player_0": False, "player_1": True, "player_2": False}
        actions = [[0, 1, 2], [9, 9, 9], [3, 4, 5]]
        step_actions = worker.getStepActions(terminated, actions)
        assert list(step_actions.keys()) == ["player_0", "player_2"]
        assert list(step_actions["player_0"]) == [0, 1, 2]
        assert list(step_actions["player_2"]) == [3, 4, 5]
    finally:
        config.SINGLE_PLAYER = original_mode


def get_step_actions_single_player_test():
    worker = _make_worker_without_init()
    original_mode = config.SINGLE_PLAYER
    config.SINGLE_PLAYER = True
    try:
        terminated = [False, True, False]
        prev_terminated = [False, False, False]
        actions = [10, 11, 12]
        step_actions = worker.getStepActions(terminated, actions, prev_terminated)
        assert step_actions == [10, 12]
    finally:
        config.SINGLE_PLAYER = original_mode


def check_greater_than_last_five_test():
    worker = _make_worker_without_init()
    assert not worker.check_greater_than_last_five([1, 1, 1, 1])
    assert not worker.check_greater_than_last_five([1, 1, 1, 1, 0])
    assert worker.check_greater_than_last_five([0, 0, 0, 1, 1, 1, 1, 1, 1])


def test_list():
    get_step_actions_parallel_test()
    get_step_actions_single_player_test()
    check_greater_than_last_five_test()
