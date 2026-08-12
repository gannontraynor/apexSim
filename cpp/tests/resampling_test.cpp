#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <limits>
#include <stdexcept>
#include <vector>

#include "apexsim/telemetry/resampling.hpp"

namespace {

using apexsim::telemetry::TelemetrySample;
using Catch::Approx;

TelemetrySample make_sample(
    const double distance_m,
    const double time_s,
    const int gear,
    const bool drs
) {
    return TelemetrySample{
        .time_s = time_s,
        .distance_m = distance_m,
        .speed_mps = distance_m * 2.0,
        .throttle = distance_m / 10.0,
        .brake = 1.0 - distance_m / 10.0,
        .gear = gear,
        .rpm = 10'000.0 + distance_m * 100.0,
        .drs = drs,
    };
}

}  // namespace

TEST_CASE("Resampling empty telemetry returns no samples") {
    const auto result = apexsim::telemetry::resample({}, 1.0);

    CHECK(result.empty());
}

TEST_CASE("Resampling a single sample returns that sample") {
    const TelemetrySample sample = make_sample(12.0, 3.0, 4, true);

    const auto result = apexsim::telemetry::resample({sample}, 1.0);

    REQUIRE(result.size() == 1);
    CHECK(result.front().distance_m == 12.0);
    CHECK(result.front().gear == 4);
    CHECK(result.front().drs);
}

TEST_CASE("Resampling linearly interpolates continuous telemetry") {
    const std::vector samples{
        make_sample(0.0, 0.0, 2, false),
        make_sample(10.0, 5.0, 4, true),
    };

    const auto result = apexsim::telemetry::resample(samples, 2.5);

    REQUIRE(result.size() == 5);
    CHECK(result[1].distance_m == Approx(2.5));
    CHECK(result[1].time_s == Approx(1.25));
    CHECK(result[1].speed_mps == Approx(5.0));
    CHECK(result[1].throttle == Approx(0.25));
    CHECK(result[1].brake == Approx(0.75));
    CHECK(result[1].rpm == Approx(10'250.0));
}

TEST_CASE("Resampling holds discrete values until their source sample") {
    const std::vector samples{
        make_sample(0.0, 0.0, 2, false),
        make_sample(5.0, 2.0, 3, true),
        make_sample(10.0, 4.0, 4, false),
    };

    const auto result = apexsim::telemetry::resample(samples, 2.5);

    REQUIRE(result.size() == 5);
    CHECK(result[1].gear == 2);
    CHECK_FALSE(result[1].drs);
    CHECK(result[2].gear == 3);
    CHECK(result[2].drs);
    CHECK(result[3].gear == 3);
    CHECK(result[3].drs);
    CHECK(result[4].gear == 4);
    CHECK_FALSE(result[4].drs);
}

TEST_CASE("Resampling includes a non-aligned final distance exactly once") {
    const std::vector samples{
        make_sample(2.0, 0.0, 2, false),
        make_sample(9.0, 3.5, 3, true),
    };

    const auto result = apexsim::telemetry::resample(samples, 3.0);

    REQUIRE(result.size() == 4);
    CHECK(result[0].distance_m == Approx(2.0));
    CHECK(result[1].distance_m == Approx(5.0));
    CHECK(result[2].distance_m == Approx(8.0));
    CHECK(result[3].distance_m == Approx(9.0));
}

TEST_CASE("A step larger than the telemetry span preserves both endpoints") {
    const std::vector samples{
        make_sample(0.0, 0.0, 2, false),
        make_sample(4.0, 2.0, 3, true),
    };

    const auto result = apexsim::telemetry::resample(samples, 10.0);

    REQUIRE(result.size() == 2);
    CHECK(result.front().distance_m == 0.0);
    CHECK(result.back().distance_m == 4.0);
}

TEST_CASE("Resampling rejects an invalid distance step") {
    const std::vector samples{make_sample(0.0, 0.0, 2, false)};

    CHECK_THROWS_AS(
        apexsim::telemetry::resample(samples, 0.0),
        std::invalid_argument
    );
    CHECK_THROWS_AS(
        apexsim::telemetry::resample(samples, -1.0),
        std::invalid_argument
    );
    CHECK_THROWS_AS(
        apexsim::telemetry::resample(
            samples,
            std::numeric_limits<double>::infinity()
        ),
        std::invalid_argument
    );
}

TEST_CASE("Resampling rejects an invalid input distance axis") {
    SECTION("duplicate distances") {
        const std::vector samples{
            make_sample(1.0, 0.0, 2, false),
            make_sample(1.0, 1.0, 3, true),
        };

        CHECK_THROWS_AS(
            apexsim::telemetry::resample(samples, 1.0),
            std::invalid_argument
        );
    }

    SECTION("decreasing distances") {
        const std::vector samples{
            make_sample(2.0, 0.0, 2, false),
            make_sample(1.0, 1.0, 3, true),
        };

        CHECK_THROWS_AS(
            apexsim::telemetry::resample(samples, 1.0),
            std::invalid_argument
        );
    }

    SECTION("non-finite distances") {
        const std::vector samples{
            make_sample(0.0, 0.0, 2, false),
            make_sample(
                std::numeric_limits<double>::quiet_NaN(),
                1.0,
                3,
                true
            ),
        };

        CHECK_THROWS_AS(
            apexsim::telemetry::resample(samples, 1.0),
            std::invalid_argument
        );
    }
}
