// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <vulkan/vulkan.hpp>

namespace Vulkan {

// The raw dumper allocates exactly four bytes per pixel and the analyzer
// decodes these bytes as 8-bit RGB(A). Never copy unsupported/HDR formats
// into that buffer: 16/32-bit float formats can require 8 or 16 B/pixel.
[[nodiscard]] constexpr const char* RawCaptureChannelOrder(vk::Format format) noexcept {
    switch (format) {
    case vk::Format::eR8G8B8A8Unorm:
    case vk::Format::eR8G8B8A8Srgb:
        return "rgba";
    case vk::Format::eB8G8R8A8Unorm:
    case vk::Format::eB8G8R8A8Srgb:
        return "bgra";
    default:
        return nullptr;
    }
}

} // namespace Vulkan
