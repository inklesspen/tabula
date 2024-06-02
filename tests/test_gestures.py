import collections.abc
from contextlib import aclosing
import typing


from tabula.commontypes import Point
from tabula.device.hwtypes import (
    TouchEvent,
    TouchReport,
    PersistentTouchReport,
    TapEvent,
    TapPhase,
)
from tabula.device.gestures import MakePersistent, TapRecognizer, make_tapstream, pump_all
from trio.lowlevel import checkpoint

T = typing.TypeVar("T")


async def make_async_source(
    items: collections.abc.Sequence[T],
):
    for item in items:
        await checkpoint()
        yield item


SIMPLE_TAP = (
    TouchReport(
        touches=[TouchEvent(x=408, y=1021, pressure=35, slot=0)],
        sec=7205,
        usec=138932,
    ),
    TouchReport(
        touches=[TouchEvent(x=408, y=1021, pressure=35, slot=0)],
        sec=7205,
        usec=149671,
    ),
    TouchReport(
        touches=[TouchEvent(x=408, y=1021, pressure=35, slot=0)],
        sec=7205,
        usec=160708,
    ),
    TouchReport(
        touches=[TouchEvent(x=409, y=1021, pressure=35, slot=0)],
        sec=7205,
        usec=175591,
    ),
    TouchReport(
        touches=[TouchEvent(x=409, y=1021, pressure=33, slot=0)],
        sec=7205,
        usec=191628,
    ),
    TouchReport(
        touches=[TouchEvent(x=409, y=1021, pressure=32, slot=0)],
        sec=7205,
        usec=207221,
    ),
    TouchReport(touches=[], sec=7205, usec=209221),
)


async def test_tap_recognition_pipeline():
    async with (
        aclosing(make_async_source(SIMPLE_TAP)) as touchsource,
        pump_all(touchsource, MakePersistent(), TapRecognizer()) as resultsource,
    ):
        actual = [event async for event in resultsource]
        expected = [
            TapEvent(location=Point(x=408, y=1021), phase=TapPhase.INITIATED),
            TapEvent(location=Point(x=409, y=1021), phase=TapPhase.COMPLETED),
        ]
        assert actual == expected


async def test_tap_recognition_tapstream():
    async with aclosing(make_async_source(SIMPLE_TAP)) as touchsource, make_tapstream(touchsource) as tapstream:
        actual = [event async for event in tapstream]
        expected = [
            TapEvent(location=Point(x=408, y=1021), phase=TapPhase.INITIATED),
            TapEvent(location=Point(x=409, y=1021), phase=TapPhase.COMPLETED),
        ]
        assert actual == expected


TOO_LIGHT = (
    TouchReport(
        touches=[TouchEvent(x=773, y=944, pressure=21, slot=0)],
        sec=13966,
        usec=125988,
    ),
    TouchReport(
        touches=[TouchEvent(x=773, y=944, pressure=22, slot=0)],
        sec=13966,
        usec=136891,
    ),
    TouchReport(
        touches=[TouchEvent(x=772, y=944, pressure=23, slot=0)],
        sec=13966,
        usec=147354,
    ),
    TouchReport(
        touches=[TouchEvent(x=772, y=944, pressure=24, slot=0)],
        sec=13966,
        usec=163191,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=944, pressure=25, slot=0)],
        sec=13966,
        usec=178754,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=944, pressure=24, slot=0)],
        sec=13966,
        usec=194660,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=944, pressure=25, slot=0)],
        sec=13966,
        usec=210599,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=944, pressure=24, slot=0)],
        sec=13966,
        usec=226484,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=944, pressure=24, slot=0)],
        sec=13966,
        usec=242367,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=944, pressure=23, slot=0)],
        sec=13966,
        usec=258412,
    ),
    TouchReport(
        touches=[TouchEvent(x=771, y=943, pressure=21, slot=0)],
        sec=13966,
        usec=273984,
    ),
    TouchReport(touches=[], sec=13966, usec=293984),
)


async def test_tap_recognition_pipeline_too_light():
    async with (
        aclosing(make_async_source(TOO_LIGHT)) as touchsource,
        pump_all(touchsource, MakePersistent(), TapRecognizer()) as resultsource,
    ):
        actual = [event async for event in resultsource]
        assert len(actual) == 0


SWIPE = (
    TouchReport(
        touches=[TouchEvent(x=764, y=753, pressure=32, slot=0)],
        sec=15456,
        usec=476973,
    ),
    TouchReport(
        touches=[TouchEvent(x=763, y=753, pressure=32, slot=0)],
        sec=15456,
        usec=487943,
    ),
    TouchReport(
        touches=[TouchEvent(x=760, y=758, pressure=32, slot=0)],
        sec=15456,
        usec=498494,
    ),
    TouchReport(
        touches=[TouchEvent(x=756, y=767, pressure=33, slot=0)],
        sec=15456,
        usec=514423,
    ),
    TouchReport(
        touches=[TouchEvent(x=749, y=784, pressure=34, slot=0)],
        sec=15456,
        usec=529480,
    ),
    TouchReport(
        touches=[TouchEvent(x=739, y=811, pressure=35, slot=0)],
        sec=15456,
        usec=545398,
    ),
    TouchReport(
        touches=[TouchEvent(x=725, y=868, pressure=35, slot=0)],
        sec=15456,
        usec=561307,
    ),
    TouchReport(
        touches=[TouchEvent(x=714, y=925, pressure=36, slot=0)],
        sec=15456,
        usec=577113,
    ),
    TouchReport(
        touches=[TouchEvent(x=706, y=967, pressure=36, slot=0)],
        sec=15456,
        usec=592972,
    ),
    TouchReport(
        touches=[TouchEvent(x=701, y=1002, pressure=36, slot=0)],
        sec=15456,
        usec=608841,
    ),
    TouchReport(
        touches=[TouchEvent(x=697, y=1028, pressure=37, slot=0)],
        sec=15456,
        usec=624860,
    ),
    TouchReport(
        touches=[TouchEvent(x=695, y=1047, pressure=37, slot=0)],
        sec=15456,
        usec=640618,
    ),
    TouchReport(
        touches=[TouchEvent(x=692, y=1062, pressure=37, slot=0)],
        sec=15456,
        usec=656259,
    ),
    TouchReport(
        touches=[TouchEvent(x=691, y=1075, pressure=37, slot=0)],
        sec=15456,
        usec=672344,
    ),
    TouchReport(
        touches=[TouchEvent(x=690, y=1084, pressure=37, slot=0)],
        sec=15456,
        usec=687861,
    ),
    TouchReport(touches=[], sec=15456, usec=697861),
)


async def test_tap_recognition_pipeline_moves_too_much():
    async with (
        aclosing(make_async_source(SWIPE)) as touchsource,
        pump_all(touchsource, MakePersistent(), TapRecognizer()) as resultsource,
    ):
        actual = [event async for event in resultsource]
        expected = [
            TapEvent(location=Point(x=764, y=753), phase=TapPhase.INITIATED),
            TapEvent(location=Point(x=749, y=784), phase=TapPhase.CANCELED),
        ]
        assert actual == expected


MULTI_TOUCH_REPORTS = (
    TouchReport(
        touches=[TouchEvent(x=763, y=1030, pressure=29, slot=0)],
        sec=7407,
        usec=339761,
    ),
    TouchReport(
        touches=[TouchEvent(x=763, y=1030, pressure=29, slot=0)],
        sec=7407,
        usec=350722,
    ),
    TouchReport(
        touches=[TouchEvent(x=763, y=1031, pressure=29, slot=0)],
        sec=7407,
        usec=361484,
    ),
    TouchReport(
        touches=[TouchEvent(x=763, y=1031, pressure=30, slot=0)],
        sec=7407,
        usec=377180,
    ),
    TouchReport(
        touches=[TouchEvent(x=763, y=1032, pressure=32, slot=0)],
        sec=7407,
        usec=392253,
    ),
    TouchReport(
        touches=[TouchEvent(x=765, y=1033, pressure=34, slot=0)],
        sec=7407,
        usec=408202,
    ),
    TouchReport(
        touches=[TouchEvent(x=766, y=1034, pressure=35, slot=0)],
        sec=7407,
        usec=424050,
    ),
    TouchReport(
        touches=[TouchEvent(x=766, y=1036, pressure=37, slot=0)],
        sec=7407,
        usec=439904,
    ),
    TouchReport(
        touches=[TouchEvent(x=767, y=1037, pressure=38, slot=0)],
        sec=7407,
        usec=455712,
    ),
    TouchReport(
        touches=[TouchEvent(x=768, y=1038, pressure=39, slot=0)],
        sec=7407,
        usec=471671,
    ),
    TouchReport(
        touches=[TouchEvent(x=768, y=1038, pressure=40, slot=0)],
        sec=7407,
        usec=487422,
    ),
    TouchReport(
        touches=[TouchEvent(x=768, y=1039, pressure=41, slot=0)],
        sec=7407,
        usec=503289,
    ),
    TouchReport(
        touches=[TouchEvent(x=768, y=1041, pressure=41, slot=0)],
        sec=7407,
        usec=519314,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=767, y=1042, pressure=41, slot=0),
            TouchEvent(x=288, y=1027, pressure=42, slot=1),
        ],
        sec=7407,
        usec=536629,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=766, y=1044, pressure=41, slot=0),
            TouchEvent(x=288, y=1027, pressure=42, slot=1),
        ],
        sec=7407,
        usec=552478,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=766, y=1045, pressure=41, slot=0),
            TouchEvent(x=289, y=1027, pressure=42, slot=1),
        ],
        sec=7407,
        usec=568316,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=766, y=1045, pressure=41, slot=0),
            TouchEvent(x=291, y=1027, pressure=42, slot=1),
        ],
        sec=7407,
        usec=584134,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=766, y=1045, pressure=41, slot=0),
            TouchEvent(x=294, y=1026, pressure=40, slot=1),
        ],
        sec=7407,
        usec=600082,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=765, y=1042, pressure=41, slot=0),
            TouchEvent(x=295, y=1024, pressure=39, slot=1),
        ],
        sec=7407,
        usec=615893,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=764, y=1040, pressure=41, slot=0),
            TouchEvent(x=297, y=1022, pressure=39, slot=1),
        ],
        sec=7407,
        usec=631814,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=762, y=1037, pressure=41, slot=0),
            TouchEvent(x=300, y=1021, pressure=39, slot=1),
        ],
        sec=7407,
        usec=647491,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=760, y=1035, pressure=41, slot=0),
            TouchEvent(x=302, y=1019, pressure=39, slot=1),
        ],
        sec=7407,
        usec=663381,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=757, y=1034, pressure=41, slot=0),
            TouchEvent(x=312, y=1017, pressure=39, slot=1),
        ],
        sec=7407,
        usec=679346,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=755, y=1034, pressure=41, slot=0),
            TouchEvent(x=326, y=1014, pressure=39, slot=1),
        ],
        sec=7407,
        usec=695105,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=755, y=1034, pressure=41, slot=0),
            TouchEvent(x=345, y=1011, pressure=39, slot=1),
        ],
        sec=7407,
        usec=711192,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=754, y=1035, pressure=41, slot=0),
            TouchEvent(x=363, y=1008, pressure=37, slot=1),
        ],
        sec=7407,
        usec=726877,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=753, y=1038, pressure=41, slot=0),
            TouchEvent(x=382, y=1005, pressure=36, slot=1),
        ],
        sec=7407,
        usec=742719,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=753, y=1040, pressure=41, slot=0),
            TouchEvent(x=400, y=1002, pressure=36, slot=1),
        ],
        sec=7407,
        usec=758461,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=753, y=1042, pressure=41, slot=0),
            TouchEvent(x=417, y=1000, pressure=36, slot=1),
        ],
        sec=7407,
        usec=774405,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=752, y=1043, pressure=41, slot=0),
            TouchEvent(x=432, y=998, pressure=36, slot=1),
        ],
        sec=7407,
        usec=790240,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=752, y=1045, pressure=41, slot=0),
            TouchEvent(x=447, y=996, pressure=36, slot=1),
        ],
        sec=7407,
        usec=806226,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=752, y=1046, pressure=41, slot=0),
            TouchEvent(x=465, y=994, pressure=36, slot=1),
        ],
        sec=7407,
        usec=821986,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=752, y=1047, pressure=41, slot=0),
            TouchEvent(x=479, y=992, pressure=36, slot=1),
        ],
        sec=7407,
        usec=837802,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=753, y=1048, pressure=41, slot=0),
            TouchEvent(x=490, y=991, pressure=36, slot=1),
        ],
        sec=7407,
        usec=853722,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=753, y=1048, pressure=41, slot=0),
            TouchEvent(x=498, y=990, pressure=36, slot=1),
        ],
        sec=7407,
        usec=869481,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=754, y=1048, pressure=41, slot=0),
            TouchEvent(x=504, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=885250,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=754, y=1048, pressure=41, slot=0),
            TouchEvent(x=509, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=901214,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=756, y=1048, pressure=42, slot=0),
            TouchEvent(x=512, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=917170,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=757, y=1048, pressure=43, slot=0),
            TouchEvent(x=515, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=932967,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=758, y=1048, pressure=43, slot=0),
            TouchEvent(x=517, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=948794,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=759, y=1049, pressure=43, slot=0),
            TouchEvent(x=519, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=964682,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=759, y=1049, pressure=43, slot=0),
            TouchEvent(x=520, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=980480,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=759, y=1049, pressure=43, slot=0),
            TouchEvent(x=520, y=989, pressure=36, slot=1),
        ],
        sec=7407,
        usec=996406,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=759, y=1045, pressure=43, slot=0),
            TouchEvent(x=520, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=12212,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=760, y=1045, pressure=43, slot=0),
            TouchEvent(x=521, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=28024,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=760, y=1046, pressure=43, slot=0),
            TouchEvent(x=521, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=43960,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=760, y=1047, pressure=43, slot=0),
            TouchEvent(x=522, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=59827,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=760, y=1048, pressure=43, slot=0),
            TouchEvent(x=522, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=75667,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=761, y=1048, pressure=43, slot=0),
            TouchEvent(x=522, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=91590,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=761, y=1049, pressure=43, slot=0),
            TouchEvent(x=523, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=107392,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=761, y=1049, pressure=43, slot=0),
            TouchEvent(x=523, y=989, pressure=36, slot=1),
        ],
        sec=7408,
        usec=123236,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=760, y=1044, pressure=43, slot=0),
            TouchEvent(x=523, y=989, pressure=37, slot=1),
        ],
        sec=7408,
        usec=139027,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=758, y=1039, pressure=39, slot=0),
            TouchEvent(x=523, y=990, pressure=38, slot=1),
        ],
        sec=7408,
        usec=154752,
    ),
    TouchReport(
        touches=[
            TouchEvent(x=756, y=1035, pressure=37, slot=0),
            TouchEvent(x=521, y=991, pressure=39, slot=1),
        ],
        sec=7408,
        usec=170400,
    ),
    TouchReport(
        touches=[TouchEvent(x=519, y=992, pressure=39, slot=1)],
        sec=7408,
        usec=186223,
    ),
    TouchReport(
        touches=[TouchEvent(x=517, y=992, pressure=39, slot=1)],
        sec=7408,
        usec=200838,
    ),
    TouchReport(
        touches=[TouchEvent(x=515, y=993, pressure=39, slot=1)],
        sec=7408,
        usec=216738,
    ),
    TouchReport(
        touches=[TouchEvent(x=514, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=232561,
    ),
    TouchReport(
        touches=[TouchEvent(x=513, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=248374,
    ),
    TouchReport(
        touches=[TouchEvent(x=513, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=264230,
    ),
    TouchReport(
        touches=[TouchEvent(x=511, y=994, pressure=40, slot=1)],
        sec=7408,
        usec=280243,
    ),
    TouchReport(
        touches=[TouchEvent(x=510, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=295925,
    ),
    TouchReport(
        touches=[TouchEvent(x=509, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=311787,
    ),
    TouchReport(
        touches=[TouchEvent(x=508, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=327670,
    ),
    TouchReport(
        touches=[TouchEvent(x=508, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=343505,
    ),
    TouchReport(
        touches=[TouchEvent(x=508, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=359415,
    ),
    TouchReport(
        touches=[TouchEvent(x=508, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=375264,
    ),
    TouchReport(
        touches=[TouchEvent(x=508, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=391081,
    ),
    TouchReport(
        touches=[TouchEvent(x=508, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=406997,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=422825,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=438578,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=454476,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=470278,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=486177,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=502047,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=517834,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=533778,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=549568,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=565392,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=581310,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=597128,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=612966,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=628777,
    ),
    TouchReport(
        touches=[TouchEvent(x=507, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=644622,
    ),
    TouchReport(
        touches=[TouchEvent(x=506, y=995, pressure=40, slot=1)],
        sec=7408,
        usec=660482,
    ),
    TouchReport(
        touches=[TouchEvent(x=505, y=994, pressure=40, slot=1)],
        sec=7408,
        usec=676307,
    ),
    TouchReport(
        touches=[TouchEvent(x=505, y=994, pressure=40, slot=1)],
        sec=7408,
        usec=692218,
    ),
    TouchReport(
        touches=[TouchEvent(x=504, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=708030,
    ),
    TouchReport(
        touches=[TouchEvent(x=504, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=723906,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=739710,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=993, pressure=40, slot=1)],
        sec=7408,
        usec=755356,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=992, pressure=40, slot=1)],
        sec=7408,
        usec=771422,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=992, pressure=40, slot=1)],
        sec=7408,
        usec=787330,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=992, pressure=40, slot=1)],
        sec=7408,
        usec=803092,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=992, pressure=40, slot=1)],
        sec=7408,
        usec=818882,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=992, pressure=38, slot=1)],
        sec=7408,
        usec=834754,
    ),
    TouchReport(
        touches=[TouchEvent(x=503, y=992, pressure=37, slot=1)],
        sec=7408,
        usec=850116,
    ),
    TouchReport(touches=[], sec=7408, usec=859116),
)


async def test_make_persistent_multitouch():
    async with (
        aclosing(make_async_source(MULTI_TOUCH_REPORTS)) as touchsource,
        pump_all(touchsource, MakePersistent()) as resultsource,
    ):
        begun = set()
        ended = set()
        seen = set()
        report: PersistentTouchReport
        async for report in resultsource:
            # first id 1 will begin
            # then id 2 will begin
            # then id 1 will end
            # then id 2 will end
            begun_ids = {pt.touch_id for pt in report.began}
            if 1 in begun_ids:
                assert begun == set()
                assert ended == set()
            if 2 in begun_ids:
                assert begun == set([1])
                assert ended == set()
            begun.update(begun_ids)
            ended_ids = {pt.touch_id for pt in report.ended}
            if 1 in ended_ids:
                assert begun == set([1, 2])
                assert ended == set()
            if 2 in ended_ids:
                assert begun == set([1, 2])
                assert ended == set([1])
            ended.update(ended_ids)
            seen.update([id(t) for t in report.began])
            seen.update([id(t) for t in report.moved])
            seen.update([id(t) for t in report.ended])
        assert len(seen) == 2
