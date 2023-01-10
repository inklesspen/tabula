from tabula.rebuild.commontypes import Point
from tabula.rebuild.hwtypes import TouchEvent, TouchReport
from tabula.rebuild.gestures import RecognitionState, TapRecognizer


def test_tap_recognition():
    reports = [
        TouchReport(
            touches=[
                TouchEvent(x=408, y=1021, pressure=35, sec=7205, usec=138932, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=408, y=1021, pressure=35, sec=7205, usec=149671, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=408, y=1021, pressure=35, sec=7205, usec=160708, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=409, y=1021, pressure=35, sec=7205, usec=175591, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=409, y=1021, pressure=33, sec=7205, usec=191628, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=409, y=1021, pressure=32, sec=7205, usec=207221, slot=0)
            ]
        ),
        TouchReport(touches=[]),
    ]
    recognizer = TapRecognizer()
    for report in reports:
        recognizer.handle_report(report)
        assert recognizer.state is not RecognitionState.FAILED
    assert recognizer.state is RecognitionState.RECOGNIZED
    assert recognizer.location == Point(x=409, y=1021)


def test_tap_recognition_too_light():
    reports = [
        TouchReport(
            touches=[
                TouchEvent(x=773, y=944, pressure=21, sec=13966, usec=125988, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=773, y=944, pressure=22, sec=13966, usec=136891, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=772, y=944, pressure=23, sec=13966, usec=147354, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=772, y=944, pressure=24, sec=13966, usec=163191, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=944, pressure=25, sec=13966, usec=178754, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=944, pressure=24, sec=13966, usec=194660, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=944, pressure=25, sec=13966, usec=210599, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=944, pressure=24, sec=13966, usec=226484, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=944, pressure=24, sec=13966, usec=242367, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=944, pressure=23, sec=13966, usec=258412, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=771, y=943, pressure=21, sec=13966, usec=273984, slot=0)
            ]
        ),
        TouchReport(touches=[]),
    ]
    recognizer = TapRecognizer()
    for report in reports:
        recognizer.handle_report(report)
    assert recognizer.state is RecognitionState.FAILED


def test_tap_recognition_moves_too_much():
    reports = [
        TouchReport(
            touches=[
                TouchEvent(x=764, y=753, pressure=32, sec=15456, usec=476973, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=763, y=753, pressure=32, sec=15456, usec=487943, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=760, y=758, pressure=32, sec=15456, usec=498494, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=756, y=767, pressure=33, sec=15456, usec=514423, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=749, y=784, pressure=34, sec=15456, usec=529480, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=739, y=811, pressure=35, sec=15456, usec=545398, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=725, y=868, pressure=35, sec=15456, usec=561307, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=714, y=925, pressure=36, sec=15456, usec=577113, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=706, y=967, pressure=36, sec=15456, usec=592972, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=701, y=1002, pressure=36, sec=15456, usec=608841, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=697, y=1028, pressure=37, sec=15456, usec=624860, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=695, y=1047, pressure=37, sec=15456, usec=640618, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=692, y=1062, pressure=37, sec=15456, usec=656259, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=691, y=1075, pressure=37, sec=15456, usec=672344, slot=0)
            ]
        ),
        TouchReport(
            touches=[
                TouchEvent(x=690, y=1084, pressure=37, sec=15456, usec=687861, slot=0)
            ]
        ),
        TouchReport(touches=[]),
    ]
    recognizer = TapRecognizer()
    for report in reports:
        recognizer.handle_report(report)
    assert recognizer.state is RecognitionState.FAILED
