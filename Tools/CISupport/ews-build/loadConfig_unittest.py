#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 Apple Inc. All rights reserved.
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

from datetime import datetime, timedelta, timezone
from twisted.internet import defer

from . import loadConfig


class ConfigDotJSONTest(unittest.TestCase):
    DUPLICATED_TRIGGERS = ['try', 'pull_request']

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

    def get_builder_from_config(self, config, builder_name):
        for builder in config['builders']:
            if builder_name == builder.get('name'):
                return builder

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
                              'defaultProperties', 'env', 'factory', 'icon', 'locks', 'name', 'platform', 'properties',
                              'rebuild_without_change_on_builder', 'remotes', 'runTests', 'shortname', 'tags', 'triggers', 'triggered_by', 'workernames', 'workerbuilddir']
        for builder in config.get('builders', []):
            for key in builder:
                self.assertTrue(key in valid_builder_keys, 'Unexpected key "{}" for builder {}'.format(key, builder.get('name')))

    def test_multiple_scheduers_for_builder(self):
        config = self.get_config()
        builder_to_schduler_map = {}
        triggered_by_schedulers = []
        for builder in config['builders']:
            triggered_by = builder.get('triggered_by')
            if triggered_by:
                triggered_by_schedulers.extend(triggered_by)

        for scheduler in config.get('schedulers'):
            if scheduler['name'] in triggered_by_schedulers:
                continue
            for buildername in scheduler.get('builderNames'):
                if scheduler.get('name') in self.DUPLICATED_TRIGGERS and builder_to_schduler_map.get(buildername):
                    self.assertTrue(builder_to_schduler_map[buildername] in self.DUPLICATED_TRIGGERS)
                else:
                    self.assertTrue(buildername not in builder_to_schduler_map, 'builder {} appears multiple times in schedulers.'.format(buildername))
                builder_to_schduler_map[buildername] = scheduler.get('name')

    def test_schduler_contains_valid_builder_name(self):
        config = self.get_config()
        builder_name_list = [builder['name'] for builder in config['builders']]
        for scheduler in config.get('schedulers'):
            for buildername in scheduler.get('builderNames'):
                self.assertTrue(buildername in builder_name_list, 'builder "{}" in scheduler "{}" is invalid.'.format(buildername, scheduler['name']))

    def test_single_builder_for_triggerable_scheduler(self):
        config = self.get_config()
        for scheduler in config['schedulers']:
            if scheduler.get('type') == 'Triggerable':
                self.assertTrue(len(scheduler.get('builderNames')) == 1, 'scheduler "{}" triggers multiple builders.'.format(scheduler['name']))

    def test_incorrect_triggered_by(self):
        config = self.get_config()
        schedulers_to_buildername_map = {}
        for scheduler in config['schedulers']:
            schedulers_to_buildername_map[scheduler['name']] = scheduler['builderNames']

        for builder in config['builders']:
            for key, value in builder.items():
                if key == 'triggered_by':
                    self.assertTrue(len(value) == 1, 'triggered_by "{}" is invalid, it should contain a single trigger.'.format(value))
                    self.assertTrue(value[0] in list(schedulers_to_buildername_map.keys()),
                                    'triggered_by "{}" for builder "{}" is not listed in schedulers section.'.format(value[0], builder['name']))

                    # Ensure that the triggered_by is correct, verify by matching that the builder for the triggered_by scheduler actually triggers current builder
                    triggered_by = value[0]
                    triggering_builder_name = schedulers_to_buildername_map.get(triggered_by)[0]
                    triggering_builder = self.get_builder_from_config(config, triggering_builder_name)
                    self.assertTrue(triggering_builder, 'builder "{}" in scheduler "{}" is invalid.'.format(triggering_builder_name, triggered_by))
                    triggering_builder_triggers = triggering_builder.get('triggers')
                    triggering_builder_triggers_buildernames = [schedulers_to_buildername_map[scheduler][0] for scheduler in triggering_builder_triggers]
                    self.assertTrue(builder['name'] in triggering_builder_triggers_buildernames,
                                    'Incorrect triggered_by "{}" in builder "{}", this builder is not in corresponding builder triggers "{}".'
                                    .format(triggered_by, builder['name'], triggering_builder_triggers_buildernames))

    def test_rebuild_without_change_only_on_builder_queues(self):
        config = self.get_config()
        for builder in config['builders']:
            if builder.get('rebuild_without_change_on_builder'):
                self.assertTrue(builder.get('triggers'), f'rebuild_without_change_on_builder should only be set on builders with triggers, but found on: {builder["name"]}')

    def test_loadBuilderConfig_output(self):
        """Regression test: verify loadBuilderConfig output counts and structure before refactoring."""
        cwd = os.path.dirname(os.path.abspath(__file__))
        c = {}
        loadConfig.loadBuilderConfig(c, is_test_mode_enabled=True, master_prefix_path=cwd)

        # Workers (count includes local-worker added in test mode)
        expected_worker_count = 234
        self.assertEqual(len(c['workers']), expected_worker_count, f"Expected {expected_worker_count} workers, got {len(c['workers'])}")
        worker_names = sorted(w.name for w in c['workers'])
        config = self.get_config()
        config_worker_names = sorted([w['name'] for w in config['workers']] + ['local-worker'])
        self.assertEqual(worker_names, config_worker_names)

        # Builders
        expected_builder_count = 46
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

        # Schedulers (count includes try_build scheduler added unconditionally)
        expected_scheduler_count = 32
        self.assertEqual(len(c['schedulers']), expected_scheduler_count, f"Expected {expected_scheduler_count} schedulers, got {len(c['schedulers'])}")
        scheduler_names = sorted(s.name for s in c['schedulers'])
        config_scheduler_names = [s['name'] for s in config['schedulers']]
        for name in config_scheduler_names:
            self.assertIn(name, scheduler_names)


class TestPrioritizeBuilders(unittest.TestCase):
    class MockBuilder(object):
        def __init__(self, name, building=False, oldestRequestTime=None):
            self.name = name
            self.building = building
            self.old_building = False
            self._oldestRequestTime = oldestRequestTime or datetime.now(timezone.utc)

        def getOldestRequestTime(self):
            return self._oldestRequestTime

    def test_builders_over_testers(self):
        builders = [
            self.MockBuilder('macOS-BigSur-Debug-Build-EWS'),
            self.MockBuilder('macOS-BigSur-Debug-WK1-Tests-EWS'),
            self.MockBuilder('macOS-BigSur-Release-Build-EWS'),
        ]
        sorted_builders = loadConfig.prioritizeBuilders(None, builders)
        self.assertEqual(
            ['macOS-BigSur-Debug-Build-EWS', 'macOS-BigSur-Release-Build-EWS', 'macOS-BigSur-Debug-WK1-Tests-EWS'],
            [builder.name for builder in sorted_builders],
        )

    def test_starvation(self):
        builders = [
            self.MockBuilder('Commit-Queue', oldestRequestTime=datetime.now(timezone.utc) - timedelta(seconds=30)),
            self.MockBuilder('Merge-Queue', oldestRequestTime=datetime.now(timezone.utc) - timedelta(seconds=10)),
            self.MockBuilder('Unsafe-Merge-Queue', oldestRequestTime=datetime.now(timezone.utc) - timedelta(seconds=60)),
        ]
        sorted_builders = loadConfig.prioritizeBuilders(None, builders)
        self.assertEqual(
            ['Unsafe-Merge-Queue', 'Commit-Queue', 'Merge-Queue'],
            [builder.name for builder in sorted_builders],
        )

    def test_starvation_prioritize_commit_queue(self):
        builders = [
            self.MockBuilder('Commit-Queue', oldestRequestTime=datetime.now(timezone.utc) - timedelta(seconds=10)),
            self.MockBuilder('Merge-Queue', oldestRequestTime=datetime.now(timezone.utc) - timedelta(seconds=60)),
            self.MockBuilder('Unsafe-Merge-Queue', oldestRequestTime=datetime.now(timezone.utc) - timedelta(seconds=20)),
        ]
        sorted_builders = loadConfig.prioritizeBuilders(None, builders)
        self.assertEqual(
            ['Unsafe-Merge-Queue', 'Commit-Queue', 'Merge-Queue'],
            [builder.name for builder in sorted_builders],
        )


class TestJsoneContext(unittest.TestCase):
    def test_jsone_context_imported(self):
        ctx = loadConfig.jsone_context()
        self.assertIn('to_entries', ctx)
        self.assertIn('group_by', ctx)
        self.assertIn('lowercase', ctx)


if __name__ == '__main__':
    unittest.main()
