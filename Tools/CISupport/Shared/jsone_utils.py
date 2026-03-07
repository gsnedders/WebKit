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

from webkitcorepy import AutoInstall, Package, Version

AutoInstall.install(Package('jsone', Version(4, 8, 2), pypi_name='json-e'))
import jsone


def jsone_context():
    return {
        'to_entries': lambda obj: [{'key': k, 'val': v} for k, v in obj.items()],
        'from_entries': lambda arr: {e['key']: e['val'] for e in arr},
        'unique': lambda arr: list(dict.fromkeys(arr)),
        'contains': lambda haystack, needle: needle in haystack,
        'keys': lambda obj: list(obj.keys()),
        'values': lambda obj: list(obj.values()),
        'startswith': lambda s, prefix: s.startswith(prefix),
        'endswith': lambda s, suffix: s.endswith(suffix),
        'lowercase': lambda s: s.lower(),
        'zfill': lambda n, width: str(n).zfill(width),
        'group_by': _jsone_group_by,
    }


def _jsone_group_by(context, arr, var_name, expr):
    """group_by(array, 'varname', 'expr') -- groups array by expression result.

    Usage in json-e: group_by(builders, 'b', 'b.platform')
    Returns {key1: [items], key2: [items], ...}.
    """
    result = {}
    for item in arr:
        sub_ctx = {**context, var_name: item}
        key = jsone.render({'$eval': expr}, sub_ctx)
        result.setdefault(str(key), []).append(item)
    return result


_jsone_group_by._jsone_builtin = True
