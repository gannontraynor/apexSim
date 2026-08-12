#include "apexsim/telemetry/resampling.hpp"

#include <cmath>
#include <stdexcept>

namespace apexsim::telemetry {
namespace {

void validate_input(
    const std::vector<TelemetrySample>& samples,
    const double distance_step_m
) {
    if (!std::isfinite(distance_step_m) || distance_step_m <= 0.0) {
        throw std::invalid_argument(
            "distance_step_m must be finite and greater than zero"
        );
    }

    for (std::size_t index = 0; index < samples.size(); ++index) {
        if (!std::isfinite(samples[index].distance_m)) {
            throw std::invalid_argument("sample distances must be finite");
        }

        if (index > 0 &&
            samples[index].distance_m <= samples[index - 1].distance_m) {
            throw std::invalid_argument(
                "sample distances must be strictly increasing"
            );
        }
    }
}

[[nodiscard]] double interpolate(
    const double start,
    const double end,
    const double fraction
) {
    return start + fraction * (end - start);
}

[[nodiscard]] TelemetrySample interpolate_sample(
    const TelemetrySample& lower,
    const TelemetrySample& upper,
    const double distance_m
) {
    const double fraction =
        (distance_m - lower.distance_m) /
        (upper.distance_m - lower.distance_m);
    const bool at_upper_sample = distance_m >= upper.distance_m;

    return TelemetrySample{
        .time_s = interpolate(lower.time_s, upper.time_s, fraction),
        .distance_m = distance_m,
        .speed_mps = interpolate(lower.speed_mps, upper.speed_mps, fraction),
        .throttle = interpolate(lower.throttle, upper.throttle, fraction),
        .brake = interpolate(lower.brake, upper.brake, fraction),
        .gear = at_upper_sample ? upper.gear : lower.gear,
        .rpm = interpolate(lower.rpm, upper.rpm, fraction),
        .drs = at_upper_sample ? upper.drs : lower.drs,
    };
}

}  // namespace

std::vector<TelemetrySample> resample(
    const std::vector<TelemetrySample>& samples,
    const double distance_step_m
) {
    validate_input(samples, distance_step_m);

    if (samples.size() < 2) {
        return samples;
    }

    const double first_distance_m = samples.front().distance_m;
    const double last_distance_m = samples.back().distance_m;
    const double distance_span_m = last_distance_m - first_distance_m;

    if (!std::isfinite(distance_span_m)) {
        throw std::invalid_argument("sample distance span must be finite");
    }

    std::vector<TelemetrySample> result;
    const auto regular_sample_count =
        static_cast<std::size_t>(std::floor(distance_span_m / distance_step_m));
    result.reserve(regular_sample_count + 2);

    std::size_t upper_index = 1;
    for (std::size_t step_index = 0; step_index <= regular_sample_count;
         ++step_index) {
        const double distance_m =
            first_distance_m +
            static_cast<double>(step_index) * distance_step_m;

        if (distance_m >= last_distance_m) {
            break;
        }

        while (samples[upper_index].distance_m < distance_m) {
            ++upper_index;
        }

        result.push_back(interpolate_sample(
            samples[upper_index - 1],
            samples[upper_index],
            distance_m
        ));
    }

    result.push_back(samples.back());
    return result;
}

}  // namespace apexsim::telemetry
