add_executable(apexsim_core_tests
    resampling_test.cpp
    telemetry_sample_test.cpp
)

target_link_libraries(apexsim_core_tests
    PRIVATE
        apexsim::core
        Catch2::Catch2WithMain
)

include(Catch)
catch_discover_tests(apexsim_core_tests)
