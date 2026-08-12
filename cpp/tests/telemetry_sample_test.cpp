#include <catch2/catch_test_macros.hpp>

#include "apexsim/telemetry/telemetry_sample.hpp"

TEST_CASE("TelemetrySample stores initialized values") {
    const apexsim::telemetry::TelemetrySample sample{
        .time_s = 1.25,
        .distance_m = 42.5,
        .speed_mps = 68.0,
        .throttle = 0.75,
        .brake = 0.1,
        .gear = 6,
        .rpm = 11'500.0,
        .drs = true,
    };

    CHECK(sample.time_s == 1.25);
    CHECK(sample.distance_m == 42.5);
    CHECK(sample.speed_mps == 68.0);
    CHECK(sample.throttle == 0.75);
    CHECK(sample.brake == 0.1);
    CHECK(sample.gear == 6);
    CHECK(sample.rpm == 11'500.0);
    CHECK(sample.drs);
}
