import queue
import time

from oddsbreaker.detect import default_detect, make_ref, usable_refs
from oddsbreaker.hunter import Hunter
from oddsbreaker.script import compile_script, parse_script
from oddsbreaker.store import default_profile
from oddsbreaker.system import StubPlatform


def make(plat, text, test=False):
    prof = default_profile("Test", "mewtwo")
    det = default_detect()
    det["region"] = [110, 30, 60, 60]
    det["refs"] = [make_ref(plat.capture(150, 70, 60, 60))]
    det["fps"] = 30
    steps, cerr = compile_script(parse_script(text)[0], prof["keys"])
    assert not cerr, cerr
    q = queue.Queue()
    return Hunter(plat, 1, steps, det, usable_refs(det), prof, q, test=test), q


def run_until(q, stop_event, limit=10):
    events = []
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            item = q.get(timeout=0.5)
        except queue.Empty:
            continue
        events.append(item[1:])
        if stop_event(item):
            break
    return events


def test_hunts_until_shiny_and_releases_keys():
    plat = StubPlatform()
    h, q = make(plat, "press A+B hold 0.01\nwait 0.01\npress A x3 gap 0.01 hold 0.01\ncheck 0.3\n")
    h.start()
    counts = []

    def stop(item):
        if item[1] == "count":
            counts.append(1)
            if len(counts) == 4:
                plat.shiny = True
        return item[1] == "state" and item[2] == "stopped"

    events = run_until(q, stop)
    names = [e[0] for e in events]
    assert "shiny" in names and len(counts) == 5
    assert "loop" in names
    downs = sorted(k for a, k in plat.log if a == "down")
    ups = sorted(k for a, k in plat.log if a == "up")
    assert downs == ups, "every key goes back up"
    assert h.sent_recently("x", within=10)


def test_stop_while_holding_a_key():
    plat = StubPlatform()
    h, q = make(plat, "hold A 5\ncheck 1")
    h.start()
    time.sleep(0.3)
    h.stop()
    h.join(2)
    assert not h.is_alive() and plat.log[-1] == ("up", "x")


def test_test_mode_runs_once_and_never_counts():
    plat = StubPlatform()
    h, q = make(plat, "press A hold 0.01\ncheck 0.3\n", test=True)
    plat.shiny = True
    h.start()
    events = run_until(q, lambda item: item[1] == "state" and item[2] == "stopped")
    names = [e[0] for e in events]
    assert "test_done" in names and "count" not in names and "shiny" not in names
    done = [e for e in events if e[0] == "test_done"][0][1]
    assert done["checks"] and done["checks"][0][1] is True


def test_closed_emulator_is_an_error():
    plat = StubPlatform()
    h, q = make(plat, "press A\ncheck 1")
    plat.windows = []
    h.start()
    events = run_until(q, lambda item: item[1] == "state" and item[2] == "stopped")
    assert any(e[0] == "error" and "closed" in e[1] for e in events)
