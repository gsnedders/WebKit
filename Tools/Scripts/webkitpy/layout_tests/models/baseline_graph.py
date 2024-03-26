import sys

if sys.version_info < (3,):
    raise ImportError("This module only supports Python 3")

import itertools
import hashlib

import networkx as nx


class BaselineGraph:
    """The graph of a given baseline file"""

    def __init__(self, filesystem, layout_test_dir, baseline_search_paths=None):
        self.fs = filesystem
        self._g = nx.DiGraph()
        self.known_platforms = {}
        self.layout_test_dir = layout_test_dir
        self._invalid_inherited = True

        if baseline_search_paths is not None:
            for baseline_search_path in baseline_search_paths:
                self.add_platform(baseline_search_path)

    def copy(self):
        g = object.__new__(BaselineGraph)
        g.fs = self.fs
        g._g = self._g.copy()
        g.known_platforms = self.known_platforms.copy()
        g.layout_test_dir = self.layout_test_dir
        self._invalid_inherited = True
        return g

    def add_platform(self, baseline_search_path):
        complete_search_path = list(baseline_search_path) + [""]
        self.known_platforms[baseline_search_path[0]] = complete_search_path
        for a, b in itertools.pairwise(complete_search_path):
            self._g.add_edge(a, b)
        self._invalid_inherited = True

    def set_baseline(self, platform, value):
        if platform not in self._g.nodes:
            raise ValueError(f"unknown platform {platform}")

        self._g.nodes[platform]["baseline"] = value
        self._invalid_inherited = True

    def remove_baseline(self, platform):
        if platform not in self._g.nodes:
            raise ValueError(f"unknown platform {platform}")

        del self._g.nodes[platform]["baseline"]
        self._invalid_inherited = True

    def get_baseline(self, platform, inherit=True):
        g = self._g

        if not inherit:
            return g.nodes[platform].get("baseline")

        for p in self.known_platforms[platform]:
            if "baseline" in g.nodes[p]:
                return g.nodes[p]["baseline"]

        return None

    def get_all_baselines(self, inherit=True, skip_missing=True):
        r = {}
        for p in self.known_platforms:
            baseline = self.get_baseline(p, inherit=inherit)
            if baseline is None and skip_missing:
                continue
            r[p] = baseline
        return r

    def _calculate_all_inherited(self):
        if not self._invalid_inherited:
            return

        g = self._g

        for nodedata in g.nodes.values():
            nodedata["inherited"] = set()

        for search_path in self.known_platforms.values():
            current_baseline = None
            for platform in reversed(search_path):
                platform_data = g.nodes[platform]
                if "baseline" in platform_data:
                    current_baseline = platform_data["baseline"]

                platform_data["inherited"].add(current_baseline)

        self._invalid_inherited = False

    def possible_baselines_for_platform(self, platform):
        return self._g.nodes[platform]["inherited"]

    def is_redundant_baseline(self, platform):
        g = self._g

        if "baseline" not in g.nodes[platform]:
            raise ValueError(f"platform {platform} doesn't have a baseline")

        self._calculate_all_inherited()
        baselines = set()
        for parent in g.successors(platform):
            baselines |= g.nodes[parent]["inherited"]

        # If we have no parent baselines, we cannot be redundant.
        if len(baselines) == 0:
            return False

        if len(baselines) == 1:
            return False

        if len(baselines) > 1 and None in baselines:
            return False

        baselines.add(g.nodes[platform]["baseline"])
        return self.files_are_same(baselines) == 1

    def remove_redundant_baselines(self):
        g = self._g

        removed = 0

        for platform, data in g.nodes.items():
            if "baseline" in data and self.is_redundant_baseline(platform):
                self.remove_baseline(platform)
                removed += 1

        return removed

    def merge_baselines(self):
        g = self._g

        possible_baselines_per_platform = {}

        for search_path in self.known_platforms.values():
            current_baseline = None
            for platform in search_path:
                platform_data = g.nodes[platform]
                if "baseline" in platform_data:
                    current_baseline = platform_data["baseline"]
                possible_baselines_per_platform.setdefault(platform, set()).add(current_baseline)

        for platform, possible_baselines in possible_baselines_per_platform.items():
            if not possible_baselines:
                continue
            
            if None in possible_baselines or not self.files_are_same(possible_baselines):
                continue

            g.nodes[platform]["baseline"] = next(iter(possible_baselines))
                
    def remove_overridden(self):
        g = self._g
        unused = {platform for platform, data in g.nodes.items() if "baseline" in data}

        for search_path in self.known_platforms.values():
            for platform in search_path:
                if "baseline" in g.nodes[platform]:
                    if platform in unused:
                        unused.remove(platform)
                    break

        for p in unused:
            self.remove_baseline(p)
        return len(unused)

    def cleanup(self):
        # Order matters below!
        removed = 0

        # Remove baselines that aren't ever used, because they just get in the way of everything else.
        removed += self.remove_overridden()

        removed = self.remove_redundant_baselines()
        self.merge_baselines()

        old = self._g.copy()
        removed = self.remove_redundant_baselines()
        assert removed < 1

        return removed

    def unique_files(self, paths):
        unique = set()

        by_size = {}
        for path in paths:
            by_size.setdefault(self.fs.getsize(path), set()).add(path)

        for size, grouped_by_size in by_size.items():
            if len(grouped_by_size) <= 1:
                unique |= grouped_by_size
                continue

            seen_hashes = set()
            for path in grouped_by_size:
                if sys.version_info >= (3, 9):
                    h = hashlib.sha1(usedforsecurity=False)
                else:
                    h = hashlib.sha1()

                # Because we store everything in a git repo, we can guarantee that we
                # don't have collisions provided we generate the same SHA-1 as git does
                # for these blobs.
                h.update(b"blob %d\0" % size)
                with self.fs.open_binary_file_for_reading(path) as f:
                    while True:
                        # Read 1 MiB at a time to keep memory under control, but this
                        # should be larger than we're ever likely to see.
                        read = f.read(1024 * 1024)
                        if not read:
                            break

                        h.update(read)

                current_hash = h.digest()
                if current_hash in seen_hashes:
                    continue

                seen_hashes.add(current_hash)
                unique.add(path)

        return unique

    def files_are_same(self, paths):
        # XXX: we can make this much quicker by exiting early in many cases
        return len(self.unique_files(paths)) == 1
