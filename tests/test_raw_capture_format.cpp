// SPDX-License-Identifier: GPL-2.0-or-later
// No Vulkan device or proprietary game data required.
#include <cassert>
#include <cstdio>
#include <string_view>
#include "video_core/renderer_vulkan/vk_raw_capture_format.h"

using Vulkan::RawCaptureChannelOrder;
using vk::Format;

static_assert(RawCaptureChannelOrder(Format::eR8G8B8A8Unorm) != nullptr);
static_assert(RawCaptureChannelOrder(Format::eR8G8B8A8Srgb) != nullptr);
static_assert(RawCaptureChannelOrder(Format::eB8G8R8A8Unorm) != nullptr);
static_assert(RawCaptureChannelOrder(Format::eB8G8R8A8Srgb) != nullptr);
static_assert(RawCaptureChannelOrder(Format::eA2R10G10B10UnormPack32) == nullptr);
static_assert(RawCaptureChannelOrder(Format::eR16G16B16A16Sfloat) == nullptr);
static_assert(RawCaptureChannelOrder(Format::eR32G32B32A32Sfloat) == nullptr);
static_assert(RawCaptureChannelOrder(Format::eD32Sfloat) == nullptr);
static_assert(RawCaptureChannelOrder(Format::eUndefined) == nullptr);

int main() {
    assert(std::string_view(RawCaptureChannelOrder(Format::eR8G8B8A8Unorm)) == "rgba");
    assert(std::string_view(RawCaptureChannelOrder(Format::eR8G8B8A8Srgb)) == "rgba");
    assert(std::string_view(RawCaptureChannelOrder(Format::eB8G8R8A8Unorm)) == "bgra");
    assert(std::string_view(RawCaptureChannelOrder(Format::eB8G8R8A8Srgb)) == "bgra");
    std::puts("raw dump format guard: OK");
}
