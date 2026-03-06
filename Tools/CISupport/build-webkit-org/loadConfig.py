# Copyright (C) 2017-2025 Apple Inc. All rights reserved.
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


import operator

from buildbot.scheduler import AnyBranchScheduler, Triggerable, Nightly
from buildbot.schedulers.forcesched import BooleanParameter, CodebaseParameter, FixedParameter, ForceScheduler, StringParameter
from buildbot.schedulers.filter import ChangeFilter

from .factories import *
from . import wkbuild, factories as _factories
from Shared.jsone_utils import jsone_context
from Shared.loadConfig_common import (BaseConfigLoader, checkValidWorker, checkValidBuilder,
    checkValidSchedulers, doesTriggerExist, isTriggerUsedByAnyBuilder,
    checkWorkersAndBuildersForConsistency, getInvalidTags, getValidTags, getTagsForBuilder)

main_filter = ChangeFilter(branch=["main", None])

BUILDER_NAME_LENGTH_LIMIT = 70
STEP_NAME_LENGTH_LIMIT = 50


def pickLatestBuild(builder, requests):
    return max(requests, key=operator.attrgetter("submittedAt"))


class PlatformSpecificScheduler(AnyBranchScheduler):
    def __init__(self, platform, branch, **kwargs):
        self.platform = platform
        filter = ChangeFilter(branch=[branch, None], filter_fn=self.filter)
        AnyBranchScheduler.__init__(self, name=platform, change_filter=filter, **kwargs)

    def filter(self, change):
        return wkbuild.should_build(self.platform, change.files)


class BWOConfigLoader(BaseConfigLoader):
    check_shortname = False

    def __init__(self):
        super().__init__(_factories)

    def get_factory_kwargs_keys(self):
        return super().get_factory_kwargs_keys() | {'device_model', 'triggered_by'}

    def get_builder_next_build(self, builder, factory_name, platform):
        if (platform.startswith('mac') or platform.startswith('ios')) and factory_name != 'BuildFactory':
            return pickLatestBuild
        return None

    def setup_schedulers(self, c, config, passwords, setup_main, setup_force):
        if setup_main:
            c['schedulers'] = []
            for scheduler in config['schedulers']:
                if 'change_filter' in scheduler:
                    scheduler['change_filter'] = globals()[scheduler['change_filter']]
                schedulerClassName = scheduler.pop('type')
                schedulerClass = globals()[schedulerClassName]
                c['schedulers'].append(schedulerClass(**scheduler))
        if setup_force:
            builderNames = [str(b['name']) for b in config['builders']]
            reason = StringParameter(name='reason', default='', size=40)
            properties = [StringParameter(name='user_provided_git_hash', label='git hash to build (optional)', required=False),
                          BooleanParameter(name='is_clean', label='Force Clean build')]
            codebases = [CodebaseParameter('',
                         revision=FixedParameter(name='revision', default=''),
                         repository=FixedParameter(name='repository', default=''),
                         project=FixedParameter(name='project', default=''),
                         branch=FixedParameter(name='branch', default=''))]
            c['schedulers'].append(ForceScheduler(name='force', builderNames=builderNames,
                                                   reason=reason, codebases=codebases, properties=properties))


def loadBuilderConfig(c, is_test_mode_enabled=False, setup_main_schedulers=True,
                      setup_force_schedulers=True, master_prefix_path=None):
    BWOConfigLoader().loadBuilderConfig(c, is_test_mode_enabled=is_test_mode_enabled,
                                        setup_main_schedulers=setup_main_schedulers,
                                        setup_force_schedulers=setup_force_schedulers,
                                        master_prefix_path=master_prefix_path)
