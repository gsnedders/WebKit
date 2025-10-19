# Copyright (C) 2020-2021 Apple Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1.  Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2.  Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY APPLE INC. AND ITS CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Callable, Iterator, Mapping, Sequence
from unittest import mock

from requests.structures import CaseInsensitiveDict

from webkitcorepy import string_utils
from webkitcorepy.mocks import ContextStack
from webkitcorepy.mocks.context_stack import ContextStack


class Response(object):
    @staticmethod
    def fromText(data: str, url: str | None = None, headers: Mapping[str, str] | None = None) -> "Response":
        assert isinstance(data, str)
        return Response(text=data, url=url, headers=headers)

    @staticmethod
    def fromJson(data: list[object] | dict[str, object], url: str | None = None, headers: Mapping[str, str] | None = None, status_code: int | None = None) -> "Response":
        assert isinstance(data, list) or isinstance(data, dict)

        merged_headers = dict(headers) if headers else {}
        if 'Content-Type' not in merged_headers:
            merged_headers['Content-Type'] = 'text/json'

        return Response(text=json.dumps(data), url=url, headers=merged_headers, status_code=status_code)

    @staticmethod
    def create404(url: str | None = None, headers: Mapping[str, str] | None = None) -> "Response":
        return Response(status_code=404, url=url, headers=headers)

    def __init__(self, status_code: int | None = None, text: str | None=None, content: bytes | None = None, url: str | None = None, headers: Mapping[str, str] | None = None) -> None:
        if status_code is not None:
            self.status_code = status_code
        elif text is not None:
            self.status_code = 200
        else:
            self.status_code = 204  # No content

        if text and content:
            raise ValueError("Cannot define both 'text' and 'content'")
        elif text:
            self.content = string_utils.encode(text)
        else:
            self.content = content or b''

        self.url = url
        self.headers: CaseInsensitiveDict[str] = CaseInsensitiveDict(headers or {})

        if 'Content-Type' not in self.headers:
            self.headers['Content-Type'] = 'text'
        if 'Content-Length' not in self.headers:
            self.headers['Content-Length'] = str(len(self.content) if self.content else 0)

    @property
    def text(self) -> str:
        return string_utils.decode(self.content)

    def json(self) -> object:
        return json.loads(self.text)

    def iter_content(self, chunk_size: int=4096) -> Iterator[str]:
        for i in range(0, len(self.text), chunk_size):
            yield self.text[i:i + chunk_size]

    def iter_lines(self) -> Iterator[bytes]:
        for line in self.text.splitlines() if self.text else []:
            yield string_utils.encode(line)

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        pass


class Requests(ContextStack):
    top = None

    def __init__(self, *hosts: Sequence[str], **kwargs: Response | Callable[..., Response]) -> None:
        super(Requests, self).__init__(cls=Requests)
        self.hosts = hosts
        self._temp_patches: list[mock._patch[Any]] = []
        self._responses = kwargs

    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        stripped_url = url.split('://')[-1]
        candidate = self._responses.get('/'.join(stripped_url.split('/')[1:]))
        if isinstance(candidate, Response):
            return candidate
        if candidate:
            return candidate(method, url, **kwargs)
        return Response.create404(url)

    def __enter__(self) -> "Requests":
        # Allow requests to be managed via autoinstall
        import requests

        this = self

        class Session(requests.Session):
            def request(self, method: str, url: str, **kwargs: Any) -> "Response | requests.Response":  # type: ignore[override]
                for host in this.hosts:
                    for candidate in ['https://{}'.format(host), 'http://{}'.format(host)]:
                        if url == candidate:
                            return this.request(method, url, **kwargs)
                        if url.startswith('{}/'.format(candidate)) or url.startswith('{}?'.format(candidate)):
                            return this.request(method, url, **kwargs)
                return super(Session, self).request(method, url, **kwargs)

        self._temp_patches = [
            mock.patch('requests.Session', new=Session),
            mock.patch('requests.request', new=lambda *args, **kwargs: Session().request(*args, **kwargs)),
            mock.patch('requests.get', new=lambda *args, **kwargs: Session().request('GET', *args, **kwargs)),
            mock.patch('requests.head', new=lambda *args, **kwargs: Session().request('HEAD', *args, **kwargs)),
            mock.patch('requests.post', new=lambda *args, **kwargs: Session().request('POST', *args, **kwargs)),
            mock.patch('requests.put', new=lambda *args, **kwargs: Session().request('PUT', *args, **kwargs)),
            mock.patch('requests.patch', new=lambda *args, **kwargs: Session().request('PATCH', *args, **kwargs)),
            mock.patch('requests.delete', new=lambda *args, **kwargs: Session().request('DELETE', *args, **kwargs)),
        ]
        for patch in self._temp_patches:
            patch.__enter__()
        return super(Requests, self).__enter__()

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        super(Requests, self).__exit__(exc_type, exc_val, exc_tb)
        for patch in reversed(self._temp_patches):
            patch.__exit__(exc_type, exc_val, exc_tb)
        self._temp_patches = []
