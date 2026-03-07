# Copyright (C) 2018-2026 Apple Inc. All rights reserved.
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


from buildbot.scheduler import AnyBranchScheduler, Periodic, Dependent, Triggerable, Nightly
from buildbot.schedulers.trysched import Try_Userpass
from buildbot.schedulers.forcesched import ForceScheduler, StringParameter, FixedParameter, CodebaseParameter
from buildbot.changes.filter import ChangeFilter
from datetime import datetime, timezone
from twisted.internet import defer

from . import factories as _factories
from .utils import get_custom_suffix
from Shared.jsone_utils import jsone_context
from Shared.loadConfig_common import (BaseConfigLoader, checkValidWorker, checkValidBuilder,
    checkValidSchedulers, doesTriggerExist, isTriggerUsedByAnyBuilder,
    checkWorkersAndBuildersForConsistency, getInvalidTags, getValidTags, getTagsForBuilder)

custom_suffix = get_custom_suffix()

BUILDER_NAME_LENGTH_LIMIT = 70
STEP_NAME_LENGTH_LIMIT = 50


# Copied from https://github.com/buildbot/buildbot/blob/master/master/buildbot/util/async_sort.py
@defer.inlineCallbacks
def async_sort(l, key, max_parallel=10):
    sem = defer.DeferredSemaphore(max_parallel)
    try:
        keys = yield defer.gatherResults([sem.run(key, i) for i in l])
    except defer.FirstError as e:
        raise e.subFailure.value

    keys = {id(l[i]): v for i, v in enumerate(keys)}
    l.sort(key=lambda x: keys[id(x)])


def prioritizeBuilders(buildmaster, builders):
    # Prioritize builder queues over tester queues.
    # Otherwise, prioritize older requests.
    # Inspired by https://docs.buildbot.net/latest/manual/customization.html#builder-priority-functions
    @defer.inlineCallbacks
    def key(b):
        request_time = yield b.getOldestRequestTime()
        return (
            'build' not in b.name.lower() and 'unsafe' not in b.name.lower() and 'commit' not in b.name.lower(),
            bool(b.building) or bool(b.old_building),
            request_time or datetime.now(timezone.utc),
        )

    async_sort(builders, key)
    return builders


class EWSConfigLoader(BaseConfigLoader):
    check_shortname = True

    def __init__(self):
        super().__init__(_factories)

    def get_factory_kwargs_keys(self):
        return super().get_factory_kwargs_keys() | {'remotes', 'runTests', 'triggered_by', 'rebuild_without_change_on_builder'}

    def setup_schedulers(self, c, config, passwords, setup_main, setup_force):
        c['prioritizeBuilders'] = prioritizeBuilders
        c['schedulers'] = []
        for scheduler in config['schedulers']:
            schedulerClassName = scheduler.pop('type')
            schedulerName = scheduler.get('name')
            schedulerClass = globals()[schedulerClassName]

            def filter_fn(change, schedulerName=schedulerName):
                return change.properties.getProperty('event') == schedulerName

            if schedulerClassName == 'Try_Userpass':
                # FIXME: Read the credentials from local file on disk.
                scheduler['userpass'] = [(passwords.get('BUILDBOT_TRY_USERNAME', 'sampleuser'), passwords.get('BUILDBOT_TRY_PASSWORD', 'samplepass'))]
            if custom_suffix != '' and schedulerName == 'safe-merge-queue' and schedulerClassName == 'Periodic':
                print(f'Testing instance, reducing safe-merge-queue scheduler frequency to avoid accumulating too many pending build-requests.')
                scheduler['periodicBuildTimer'] = 24 * 60 * 60
            if schedulerClassName == 'AnyBranchScheduler' and schedulerName:
                scheduler['change_filter'] = ChangeFilter(filter_fn=filter_fn)
            if setup_main:
                c['schedulers'].append(schedulerClass(**scheduler))

        if setup_force:
            c['schedulers'].append(ForceScheduler(
                name='try_build',
                buttonName='Try Build',
                reason=StringParameter(name='reason', default='Trying pull request', size=20),
                builderNames=[str(builder['name']) for builder in config['builders']],
                # Disable default enabled input fields: branch, repository, project, additional properties
                codebases=[CodebaseParameter('',
                           revision=FixedParameter(name='revision', default=''),
                           repository=FixedParameter(name='repository', default=''),
                           project=FixedParameter(name='project', default=''),
                           branch=FixedParameter(name='branch', default=''))],
                # Add custom properties needed
                properties=[StringParameter(name='pr_number', label='Pull Request number (not bug number)', regex=r'^[0-9]{5,6}$', required=True, maxsize=6),
                            StringParameter(name='ews_revision', label='WebKit git hash to checkout before trying patch (optional)', required=False, maxsize=40)],
            ))


def loadBuilderConfig(c, is_test_mode_enabled=False, setup_main_schedulers=True, setup_force_schedulers=True, master_prefix_path=None):
    EWSConfigLoader().loadBuilderConfig(c, is_test_mode_enabled=is_test_mode_enabled,
                                        setup_main_schedulers=setup_main_schedulers,
                                        setup_force_schedulers=setup_force_schedulers,
                                        master_prefix_path=master_prefix_path)
