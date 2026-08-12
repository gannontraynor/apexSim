#pragma once

namespace apexsim::telemetry {

struct TelemetrySample {
    double time_s{};
    double distance_m{};

    double speed_mps{};
    double throttle{};
    double brake{};

    int gear{};
    double rpm{};

    bool drs{};
};

}  // namespace apexsim::telemetry
