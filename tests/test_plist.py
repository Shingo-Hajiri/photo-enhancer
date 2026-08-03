import plistlib
from pathlib import Path


def test_launchd_plist_is_valid_and_scheduled_correctly():
    plist_path = Path(__file__).parent.parent / "com.sweets.photoenhancer.plist"
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["Label"] == "com.sweets.photoenhancer"
    intervals = data["StartCalendarInterval"]
    assert len(intervals) == 2
    times = sorted((entry["Hour"], entry["Minute"]) for entry in intervals)
    assert times == [(22, 0), (23, 30)]
