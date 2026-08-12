#pragma once

#include <vector>

#include "apexsim/telemetry/telemetry_sample.hpp"

namespace apexsim::telemetry {

[[nodiscard]] std::vector<TelemetrySample> resample(
    const std::vector<TelemetrySample>& samples,
    double distance_step_m
);

}  // namespace apexsim::telemetry
