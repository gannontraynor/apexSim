cmake_minimum_required(VERSION 3.20)

project(ApexSimCore VERSION 0.1.0 LANGUAGES CXX)

include(CTest)
include(FetchContent)

add_library(apexsim_core
    src/telemetry/resampling.cpp
    src/telemetry/telemetry_sample.cpp
)

add_library(apexsim::core ALIAS apexsim_core)

target_compile_features(apexsim_core PUBLIC cxx_std_20)

target_include_directories(apexsim_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

add_executable(apexsim_resample_csv
    apps/resample_csv.cpp
)

target_link_libraries(apexsim_resample_csv PRIVATE apexsim::core)

if(BUILD_TESTING)
    FetchContent_Declare(
        Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG v3.8.1
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(Catch2)

    add_subdirectory(tests)
endif()
