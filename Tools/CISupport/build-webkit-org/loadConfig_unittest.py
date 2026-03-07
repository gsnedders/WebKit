#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 Apple Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1.  Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
# 2.  Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY APPLE INC. AND ITS CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import json
import os
import unittest

from . import loadConfig


class ConfigDotJSONTest(unittest.TestCase):
    def get_config(self):
        return self._render_config()

    def _render_config(self):
        import jsone
        cwd = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(cwd, 'config.json')) as f:
            raw_config = json.load(f)
        ctx = loadConfig.jsone_context()
        builders = jsone.render(raw_config['builders'], ctx)
        schedulers = jsone.render(raw_config['schedulers'], {**ctx, 'builders': builders})
        workers = jsone.render(raw_config['workers'], ctx)
        return {'workers': workers, 'builders': builders, 'schedulers': schedulers}

    def test_configuration(self):
        cwd = os.path.dirname(os.path.abspath(__file__))
        loadConfig.loadBuilderConfig({}, is_test_mode_enabled=True, master_prefix_path=cwd)

    def test_tab_character(self):
        cwd = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(cwd, 'config.json'), 'r') as config:
            self.assertTrue('\t' not in config.read(), 'Tab character found in config.json, please use spaces instead of tabs.')

    def test_jsone_rendering_produces_flat_arrays(self):
        rendered = self._render_config()
        self.assertIsInstance(rendered['workers'], list)
        self.assertIsInstance(rendered['builders'], list)
        self.assertIsInstance(rendered['schedulers'], list)
        for w in rendered['workers']:
            self.assertIn('name', w)
            self.assertIn('platform', w)
        for b in rendered['builders']:
            self.assertIn('name', b)

    def test_builder_keys(self):
        config = self.get_config()
        valid_builder_keys = ['additionalArguments', 'architectures', 'builddir', 'configuration', 'description',
                              'defaultProperties', 'device_model', 'env', 'factory', 'icon', 'locks', 'name', 'platform', 'properties',
                              'remotes', 'runTests', 'shortname', 'tags', 'triggered_by', 'triggers', 'workernames', 'workerbuilddir']
        for builder in config.get('builders', []):
            for key in builder:
                self.assertTrue(key in valid_builder_keys, f"Unexpected key {key} for builder {builder.get('name')}")

    def test_multiple_scheduers_for_builder(self):
        config = self.get_config()
        builder_to_schduler_map = {}

        for scheduler in config.get('schedulers'):
            for buildername in scheduler.get('builderNames'):
                self.assertTrue(buildername not in builder_to_schduler_map, f'builder {buildername} appears multiple times in schedulers.')
                builder_to_schduler_map[buildername] = scheduler.get('name')

    def test_schduler_contains_valid_builder_name(self):
        config = self.get_config()
        builder_name_list = [builder['name'] for builder in config['builders']]
        for scheduler in config.get('schedulers'):
            for buildername in scheduler.get('builderNames'):
                self.assertTrue(buildername in builder_name_list, f"builder {buildername} in scheduler {scheduler.get('name')} is invalid.")

    def test_single_builder_for_triggerable_scheduler(self):
        config = self.get_config()
        for scheduler in config['schedulers']:
            if scheduler.get('type') == 'Triggerable':
                self.assertTrue(len(scheduler.get('builderNames')) == 1, f"scheduler {scheduler['name']} triggers multiple builders.")

    def test_loadBuilderConfig_output(self):
        """Regression test: verify loadBuilderConfig output counts and structure before refactoring."""
        cwd = os.path.dirname(os.path.abspath(__file__))
        c = {}
        loadConfig.loadBuilderConfig(c, is_test_mode_enabled=True, master_prefix_path=cwd)

        # Workers (count includes local-worker added in test mode)
        expected_worker_count = 176
        self.assertEqual(len(c['workers']), expected_worker_count, f"Expected {expected_worker_count} workers, got {len(c['workers'])}")
        worker_names = sorted(w.name for w in c['workers'])
        config = self.get_config()
        config_worker_names = sorted([w['name'] for w in config['workers']] + ['local-worker'])
        self.assertEqual(worker_names, config_worker_names)

        # Builders
        expected_builder_count = 100
        self.assertEqual(len(c['builders']), expected_builder_count, f"Expected {expected_builder_count} builders, got {len(c['builders'])}")
        builder_names = sorted(b['name'] for b in c['builders'])
        config_builder_names = sorted(b['name'] for b in config['builders'])
        self.assertEqual(builder_names, config_builder_names)
        for builder in c['builders']:
            self.assertIsNotNone(builder.get('factory'))
            self.assertIsInstance(builder.get('tags'), list)

        # Factory type names per builder (catches wrong factory being used)
        factory_types = {b['name']: type(b['factory']).__name__ for b in c['builders']}
        for name, factory_type in factory_types.items():
            self.assertIsNotNone(factory_type, f"Builder {name} has no factory type")

        # Schedulers (count includes force scheduler added unconditionally)
        expected_scheduler_count = 65
        self.assertEqual(len(c['schedulers']), expected_scheduler_count, f"Expected {expected_scheduler_count} schedulers, got {len(c['schedulers'])}")
        scheduler_names = sorted(s.name for s in c['schedulers'])
        config_scheduler_names = [s['name'] for s in config['schedulers'] if 'name' in s]
        for name in config_scheduler_names:
            self.assertIn(name, scheduler_names)

        # nextBuild is set only for non-Build AppleMac/iOS builders
        builders_with_next_build = sorted(b['name'] for b in c['builders'] if 'nextBuild' in b)
        for name in builders_with_next_build:
            self.assertTrue(
                any(name.startswith(p) for p in ('Apple-Tahoe', 'Apple-Sequoia', 'Apple-iOS', 'Apple-iPadOS', 'Apple-visionOS')),
                f"Unexpected nextBuild on {name}"
            )


class TestJsoneContext(unittest.TestCase):
    def test_jsone_context_imported(self):
        ctx = loadConfig.jsone_context()
        self.assertIn('to_entries', ctx)
        self.assertIn('group_by', ctx)
        self.assertIn('lowercase', ctx)


if __name__ == '__main__':
    from steps_unittest_old import BuildBotConfigLoader
    BuildBotConfigLoader()._add_dependent_modules_to_sys_modules()
    import loadConfig
    unittest.main()
