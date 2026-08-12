#include <array>
#include <cerrno>
#include <charconv>
#include <cstddef>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <vector>

#include "apexsim/telemetry/resampling.hpp"

namespace {

using apexsim::telemetry::TelemetrySample;

constexpr std::string_view expected_header =
    "time_s,distance_m,speed_mps,throttle,brake,gear,rpm,drs";

[[nodiscard]] std::array<std::string_view, 8> split_row(
    const std::string& row,
    const std::size_t line_number
) {
    std::array<std::string_view, 8> fields;
    std::size_t field_index = 0;
    std::size_t field_start = 0;

    for (std::size_t index = 0; index <= row.size(); ++index) {
        if (index != row.size() && row[index] != ',') {
            continue;
        }

        if (field_index >= fields.size()) {
            throw std::runtime_error(
                "too many CSV fields on line " + std::to_string(line_number)
            );
        }

        fields[field_index] =
            std::string_view(row).substr(field_start, index - field_start);
        ++field_index;
        field_start = index + 1;
    }

    if (field_index != fields.size()) {
        throw std::runtime_error(
            "expected 8 CSV fields on line " + std::to_string(line_number)
        );
    }

    return fields;
}

template <typename Value>
[[nodiscard]] Value parse_number(
    const std::string_view field,
    const std::size_t line_number
) {
    if constexpr (std::is_floating_point_v<Value>) {
        const std::string text(field);
        char* end = nullptr;
        errno = 0;
        const double value = std::strtod(text.c_str(), &end);

        if (errno == ERANGE || end != text.c_str() + text.size()) {
            throw std::runtime_error(
                "invalid numeric value on line " + std::to_string(line_number)
            );
        }

        return static_cast<Value>(value);
    } else {
        Value value{};
        const auto [end, error] =
            std::from_chars(field.data(), field.data() + field.size(), value);

        if (error != std::errc{} || end != field.data() + field.size()) {
            throw std::runtime_error(
                "invalid numeric value on line " + std::to_string(line_number)
            );
        }

        return value;
    }
}

[[nodiscard]] std::vector<TelemetrySample> read_samples(
    const std::string& input_path
) {
    std::ifstream input(input_path);
    if (!input) {
        throw std::runtime_error("unable to open input CSV: " + input_path);
    }

    std::string row;
    if (!std::getline(input, row) || row != expected_header) {
        throw std::runtime_error(
            "input CSV header must be: " + std::string(expected_header)
        );
    }

    std::vector<TelemetrySample> samples;
    std::size_t line_number = 1;
    while (std::getline(input, row)) {
        ++line_number;
        if (row.empty()) {
            continue;
        }

        const auto fields = split_row(row, line_number);
        const int drs = parse_number<int>(fields[7], line_number);
        if (drs != 0 && drs != 1) {
            throw std::runtime_error(
                "DRS must be 0 or 1 on line " + std::to_string(line_number)
            );
        }

        samples.push_back(TelemetrySample{
            .time_s = parse_number<double>(fields[0], line_number),
            .distance_m = parse_number<double>(fields[1], line_number),
            .speed_mps = parse_number<double>(fields[2], line_number),
            .throttle = parse_number<double>(fields[3], line_number),
            .brake = parse_number<double>(fields[4], line_number),
            .gear = parse_number<int>(fields[5], line_number),
            .rpm = parse_number<double>(fields[6], line_number),
            .drs = drs == 1,
        });
    }

    return samples;
}

void write_samples(
    const std::string& output_path,
    const std::vector<TelemetrySample>& samples
) {
    std::ofstream output(output_path);
    if (!output) {
        throw std::runtime_error("unable to open output CSV: " + output_path);
    }

    output << expected_header << '\n' << std::setprecision(15);
    for (const auto& sample : samples) {
        output << sample.time_s << ',' << sample.distance_m << ','
               << sample.speed_mps << ',' << sample.throttle << ','
               << sample.brake << ',' << sample.gear << ',' << sample.rpm << ','
               << static_cast<int>(sample.drs) << '\n';
    }
}

[[nodiscard]] double parse_step(const std::string_view argument) {
    return parse_number<double>(argument, 0);
}

}  // namespace

int main(const int argc, const char* const argv[]) {
    if (argc != 4) {
        std::cerr << "Usage: apexsim_resample_csv INPUT.csv OUTPUT.csv "
                     "DISTANCE_STEP_M\n";
        return 2;
    }

    try {
        const auto samples = read_samples(argv[1]);
        const auto result = apexsim::telemetry::resample(
            samples,
            parse_step(argv[3])
        );
        write_samples(argv[2], result);
        std::cout << "Resampled " << samples.size() << " samples to "
                  << result.size() << " samples.\n";
    } catch (const std::exception& error) {
        std::cerr << "Resampling failed: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
