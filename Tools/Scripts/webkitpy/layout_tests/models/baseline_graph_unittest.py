import itertools

from hypothesis import given, settings, event, assume, example
from hypothesis.strategies import (
    composite,
    lists,
    sampled_from,
    sets,
    integers,
    dictionaries,
    permutations,
)

from pyfakefs import fake_filesystem_unittest

from webkitpy.common.system.filesystem import FileSystem
from webkitpy.layout_tests.models.baseline_graph import BaselineGraph


# This is ordered to be roughly grouped by platform, but having shorter search paths
# first (because hypothesis.strategies.sampled_from shrinks towards earlier items, and a
# shorter path is easier to understand!).
known_baseline_search_path = [
    ("platform/gtk", "platform/glib", "platform/wk2"),
    ("platform/gtk4", "platform/gtk", "platform/glib", "platform/wk2"),
    ("platform/gtk-wayland", "platform/gtk", "platform/glib", "platform/wk2"),
    ("platform/wpe", "platform/glib", "platform/wk2"),
    (
        "platform/wincairo-win10-wk2",
        "platform/wincairo-win10",
        "platform/wincairo-wk2",
        "platform/wincairo",
        "platform/wk2",
    ),
    (
        "platform/mac-sonoma-wk1",
        "platform/mac-sonoma",
        "platform/mac-wk1",
        "platform/mac",
    ),
    (
        "platform/mac-sonoma-wk2",
        "platform/mac-sonoma",
        "platform/mac-wk2",
        "platform/mac",
        "platform/wk2",
    ),
    (
        "platform/mac-ventura-wk1",
        "platform/mac-ventura",
        "platform/mac-wk1",
        "platform/mac",
    ),
    (
        "platform/mac-ventura-wk2",
        "platform/mac-ventura",
        "platform/mac-wk2",
        "platform/mac",
        "platform/wk2",
    ),
    (
        "platform/mac-monterey-wk1",
        "platform/mac-monterey",
        "platform/mac-ventura-wk1",
        "platform/mac-ventura",
        "platform/mac-wk1",
        "platform/mac",
    ),
    (
        "platform/mac-monterey-wk2",
        "platform/mac-monterey",
        "platform/mac-ventura-wk2",
        "platform/mac-ventura",
        "platform/mac-wk2",
        "platform/mac",
        "platform/wk2",
    ),
    (
        "platform/ios-simulator-wk2",
        "platform/ios-simulator",
        "platform/ios-wk2",
        "platform/ios",
        "platform/wk2",
    ),
    (
        "platform/ipad-simulator-wk2",
        "platform/ipad-simulator",
        "platform/ios-simulator-wk2",
        "platform/ios-simulator",
        "platform/ipad-wk2",
        "platform/ipad",
        "platform/ios-wk2",
        "platform/ios",
        "platform/wk2",
    ),
]


@composite
def subsequences(draw, sequence, min_size=0, max_size=None):
    if max_size is None:
        max_size = len(sequence)

    if min_size > max_size:
        raise ValueError("min_size > max_size")

    include = draw(
        sets(integers(0, len(sequence) - 1), min_size=min_size, max_size=max_size)
    )
    return [x for i, x in enumerate(sequence) if i in include]


@composite
def baseline_graph_data(draw):
    baseline_search_paths = draw(
        sets(sampled_from(known_baseline_search_path), min_size=1)
    )

    all_platforms = [""] + sorted(
        set(itertools.chain.from_iterable(baseline_search_paths))
    )

    platforms_with_baselines = draw(sets(sampled_from(all_platforms)))

    if platforms_with_baselines:
        # Note we choose the count of non-unique so when we shrink towards zero, we
        # shrink towards everything being unique.
        non_unique_baselines = draw(integers(0, len(platforms_with_baselines) - 1))
        baseline_data = [
            chr(ord("A") + x)
            for x in range(
                len(platforms_with_baselines) - non_unique_baselines,
            )
        ]
        assert len(baseline_data) > 0

        platform_baseline_data = draw(
            permutations(
                list(
                    itertools.islice(
                        itertools.cycle(baseline_data), len(platforms_with_baselines)
                    )
                )
            )
        )

        assert len(platforms_with_baselines) == len(platform_baseline_data)

        baselines = dict(zip(platforms_with_baselines, platform_baseline_data))
    else:
        baselines = {}

    return (baseline_search_paths, baselines)


def baseline_graph_factory(baseline_search_paths, baselines):
    fs = FileSystem()
    layout_tests_dir = str(fs.mkdtemp())
    graph = BaselineGraph(fs, layout_tests_dir, baseline_search_paths)
    for baseline, content in baselines.items():
        baseline = "" if not baseline else baseline
        path = fs.join(layout_tests_dir, baseline, "test-expected.txt")
        fs.maybe_make_directory(fs.dirname(path))
        fs.write_text_file(path, content)
        graph.set_baseline(baseline, path)
    return graph


class BaselineGraphTests(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def assertIdenticalBaselines(self, fs, old, new):
        old_baselines = {
            k: fs.read_text_file(v) for k, v in old.get_all_baselines().items()
        }
        new_baselines = {
            k: fs.read_text_file(v) for k, v in new.get_all_baselines().items()
        }
        assert old_baselines == new_baselines

    @given(baseline_graph_data())
    @example(
        (
            [
                ("platform/ipad", "platform/ios"),
                (
                    "platform/ipad-wk2",
                    "platform/ipad",
                    "platform/ios-wk2",
                    "platform/ios",
                ),
            ],
            {"platform/ipad": "A", "platform/ios-wk2": "B", "": "A"},
        )
    )
    @settings(max_examples=1000, deadline=None)
    def test_remove_redundant(self, data):
        graph = baseline_graph_factory(*data)
        fs = graph.fs
        old = graph.copy()
        removed = graph.remove_redundant_baselines()
        event("removed", removed)
        self.assertIdenticalBaselines(fs, old, graph)

    @given(baseline_graph_data())
    @settings(max_examples=1000, deadline=None)
    def test_remove_overridden(self, data):
        graph = baseline_graph_factory(*data)
        fs = graph.fs
        old = graph.copy()
        removed = graph.remove_overridden()
        event("removed", removed)
        self.assertIdenticalBaselines(fs, old, graph)

    @given(baseline_graph_data())
    @settings(max_examples=5000, deadline=None)
    def test_cleanup(self, data):
        graph = baseline_graph_factory(*data)
        fs = graph.fs
        old = graph.copy()
        removed = graph.cleanup()
        event("removed", removed)
        self.assertIdenticalBaselines(fs, old, graph)
