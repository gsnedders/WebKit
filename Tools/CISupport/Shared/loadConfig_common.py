# Copyright (C) 2025 Apple Inc. All rights reserved.
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
import re
from abc import ABC, abstractmethod

from buildbot.util import identifiers as buildbot_identifiers
from buildbot.worker import Worker

from Shared.jsone_utils import jsone_context
from webkitcorepy import AutoInstall, Package, Version

AutoInstall.install(Package('jsone', Version(4, 8, 2), pypi_name='json-e'))
import jsone

BUILDER_NAME_LENGTH_LIMIT = 70
STEP_NAME_LENGTH_LIMIT = 50


class BaseConfigLoader(ABC):
    check_shortname = False

    def __init__(self, factories):
        self.factories = factories

    def get_factory(self, name):
        return getattr(self.factories, name)

    def get_factory_kwargs_keys(self):
        return {'platform', 'configuration', 'architectures', 'triggers', 'additionalArguments'}

    def get_builder_next_build(self, builder, factory_name, platform):
        """Return nextBuild callback for this builder, or None for buildbot default."""
        return None

    @abstractmethod
    def setup_schedulers(self, c, config, passwords, setup_main, setup_force):
        """Set up c['schedulers']. Must be implemented by subclass."""

    def loadBuilderConfig(self, c, is_test_mode_enabled=False, setup_main_schedulers=True,
                          setup_force_schedulers=True, master_prefix_path=None):
        if not master_prefix_path:
            master_prefix_path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(master_prefix_path, 'config.json')) as f:
            raw_config = json.load(f)

        # Render json-e templates
        ctx = jsone_context()
        workers_rendered = jsone.render(raw_config['workers'], ctx)
        builders_rendered = jsone.render(raw_config['builders'], ctx)
        schedulers_rendered = jsone.render(raw_config['schedulers'], {**ctx, 'builders': builders_rendered})
        config = {**raw_config, 'workers': workers_rendered, 'builders': builders_rendered, 'schedulers': schedulers_rendered}

        if is_test_mode_enabled:
            passwords = {}
        else:
            passwords = json.load(open(os.path.join(master_prefix_path, 'passwords.json')))
        results_server_api_key = passwords.get('results-server-api-key')
        if results_server_api_key:
            os.environ['RESULTS_SERVER_API_KEY'] = results_server_api_key

        checkWorkersAndBuildersForConsistency(config, config['workers'], config['builders'],
                                              check_shortname=self.check_shortname)
        checkValidSchedulers(config, config['schedulers'])

        c['workers'] = [Worker(worker['name'], passwords.get(worker['name'], 'password'),
                               max_builds=worker.get('max_builds', 1))
                        for worker in config['workers']]
        if is_test_mode_enabled:
            c['workers'].append(Worker('local-worker', 'password', max_builds=1))

        c['builders'] = []
        for builder in config['builders']:
            builder['tags'] = getTagsForBuilder(builder)
            factory_name = builder.pop('factory')
            factory = self.get_factory(factory_name)
            if builder.get('shortname'):
                builder['description'] = builder.pop('shortname')
            if 'icon' in builder:
                del builder['icon']
            factorykwargs = {}
            for key in self.get_factory_kwargs_keys():
                value = builder.pop(key, None)
                if value:
                    factorykwargs[key] = value
            builder['factory'] = factory(**factorykwargs)
            if is_test_mode_enabled:
                builder['workernames'].append('local-worker')
            for step in builder['factory'].steps:
                step_name = step.buildStep().name
                if len(step_name) > STEP_NAME_LENGTH_LIMIT:
                    raise Exception(f'step name "{step_name}" is longer than maximum allowed by Buildbot ({STEP_NAME_LENGTH_LIMIT} characters).')
                if not buildbot_identifiers.ident_re.match(step_name):
                    raise Exception(f'step name "{step_name}" is not a valid buildbot identifier.')
            next_build = self.get_builder_next_build(builder, factory_name, factorykwargs.get('platform', ''))
            if next_build is not None:
                builder['nextBuild'] = next_build
            c['builders'].append(builder)

        self.setup_schedulers(c, config, passwords, setup_main_schedulers, setup_force_schedulers)


def checkValidWorker(worker):
    if not worker:
        raise Exception('Worker is None or Empty.')

    if not worker.get('name'):
        raise Exception(f'Worker "{worker}" does not have name defined.')

    if not worker.get('platform'):
        raise Exception(f"Worker {worker['name']} does not have platform defined.")


def checkValidBuilder(config, builder, check_shortname=False):
    if not builder:
        raise Exception('Builder is None or Empty.')

    if not builder.get('name'):
        raise Exception(f'Builder "{builder}" does not have name defined.')

    if check_shortname and not builder.get('shortname'):
        raise Exception(f'Builder "{builder.get("name")}" does not have short name defined. This name is needed for EWS status bubbles.')

    if not buildbot_identifiers.ident_re.match(builder['name']):
        raise Exception(f"Builder name {builder['name']} is not a valid buildbot identifier.")

    if len(builder['name']) > BUILDER_NAME_LENGTH_LIMIT:
        raise Exception(f"Builder name {builder['name']} is longer than maximum allowed by Buildbot ({BUILDER_NAME_LENGTH_LIMIT} characters).")

    if 'configuration' in builder and builder['configuration'] not in ['debug', 'production', 'release']:
        raise Exception(f"Invalid configuration: {builder.get('configuration')} for builder: {builder.get('name')}")

    if not builder.get('factory'):
        raise Exception(f"Builder {builder['name']} does not have factory defined.")

    if not builder.get('platform'):
        raise Exception(f"Builder {builder['name']} does not have platform defined.")

    for trigger in builder.get('triggers') or []:
        if not doesTriggerExist(config, trigger):
            raise Exception(f"Trigger: {trigger} in builder {builder['name']} does not exist in list of Trigerrable schedulers.")

    if builder.get('rebuild_without_change_on_builder') and not builder.get('triggers'):
        raise Exception(f'rebuild_without_change_on_builder can only be set on builders with triggers. Builder: {builder["name"]}')


def checkValidSchedulers(config, schedulers):
    for scheduler in config.get('schedulers') or []:
        if scheduler.get('type') == 'Triggerable':
            if not isTriggerUsedByAnyBuilder(config, scheduler['name']) and 'build' not in scheduler['name'].lower():
                raise Exception(f"Trigger: {scheduler['name']} is not used by any builder in config.json")


def doesTriggerExist(config, trigger):
    for scheduler in config.get('schedulers') or []:
        if scheduler.get('name') == trigger:
            return True
    return False


def isTriggerUsedByAnyBuilder(config, trigger):
    for builder in config.get('builders'):
        if trigger in (builder.get('triggers') or []):
            return True
    return False


def checkWorkersAndBuildersForConsistency(config, workers, builders, check_shortname=False):
    def _find_worker_with_name(workers, worker_name):
        result = None
        for worker in workers:
            if worker['name'] == worker_name:
                if not result:
                    result = worker
                else:
                    raise Exception(f"Duplicate worker entry found for {worker['name']}.")
        return result

    for worker in workers:
        checkValidWorker(worker)

    for builder in builders:
        checkValidBuilder(config, builder, check_shortname=check_shortname)
        for worker_name in builder['workernames']:
            worker = _find_worker_with_name(workers, worker_name)
            if worker is None:
                raise Exception(f"Builder {builder['name']} has worker {worker_name}, which is not defined in workers list!")

            if worker['platform'] != builder['platform'] and worker['platform'] != '*' and builder['platform'] != '*':
                raise Exception(f"Builder {builder['name']} is for platform {builder['platform']}, but has worker {worker['name']} for platform {worker['platform']}!")


def getInvalidTags():
    """
    We maintain a list of words which we do not want to display as tag in buildbot.
    We generate a list of tags by splitting the builder name. We do not want certain words as tag.
    For e.g. we don't want '11'as tag for builder iOS-11-Simulator-EWS
    """
    invalid_tags = [str(i) for i in range(0, 20)]
    invalid_tags.extend(['EWS', 'TryBot'])
    return invalid_tags


def getValidTags(tags):
    return list(set(tags) - set(getInvalidTags()))


def getTagsForBuilder(builder):
    keywords = re.split(r'[, \-_:()]+', str(builder['name']))
    return getValidTags(keywords)
