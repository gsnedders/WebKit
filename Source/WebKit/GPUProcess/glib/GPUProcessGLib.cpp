/*
 * Copyright (C) 2020 Igalia S.L.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS''
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS
 * BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
 * THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "config.h"
#include "GPUProcess.h"

#if ENABLE(GPU_PROCESS) && (PLATFORM(GTK) || PLATFORM(WPE))

#include "GPUProcessCreationParameters.h"

#if USE(GBM)
#include <WebCore/DRMDeviceManager.h>
#include <WebCore/PlatformDisplayGBM.h>
#endif

namespace WebKit {

void GPUProcess::platformInitializeGPUProcess(GPUProcessCreationParameters& parameters)
{
#if USE(GBM)
    WebCore::DRMDeviceManager::singleton().initializeMainDevice(parameters.renderDeviceFile);

    if (auto* device = WebCore::DRMDeviceManager::singleton().mainGBMDeviceNode(WebCore::DRMDeviceManager::NodeType::Render)) {
        WebCore::PlatformDisplay::setSharedDisplay(WebCore::PlatformDisplayGBM::create(device));
        return;
    }
#else
    UNUSED_PARAM(parameters);
#endif

    WTFLogAlways("Could not create EGL display for GPU process: no supported platform available. Aborting...");
    CRASH();
}

void GPUProcess::initializeProcess(const AuxiliaryProcessInitializationParameters&)
{
}

void GPUProcess::initializeProcessName(const AuxiliaryProcessInitializationParameters&)
{
}

void GPUProcess::initializeSandbox(const AuxiliaryProcessInitializationParameters&, SandboxInitializationParameters&)
{
}

} // namespace WebKit

#endif // ENABLE(GPU_PROCESS) && (PLATFORM(GTK) || PLATFORM(WPE))
