cmake_minimum_required(VERSION 3.20)
project(px4_reqcheck_cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.12.0
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(nlohmann_json)

add_library(descent src/descent.cpp)
target_include_directories(descent PUBLIC include)
target_compile_options(descent PRIVATE -Wall -Wextra -Werror)

add_executable(px4-reqcheck-cpp src/main.cpp)
target_link_libraries(px4-reqcheck-cpp PRIVATE descent nlohmann_json::nlohmann_json)
target_compile_options(px4-reqcheck-cpp PRIVATE -Wall -Wextra -Werror)

option(BUILD_TESTING "Build tests" ON)
if(BUILD_TESTING)
  include(CTest)
  FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.17.0
    GIT_SHALLOW TRUE
  )
  FetchContent_MakeAvailable(googletest)
  add_executable(descent_test tests/descent_test.cpp)
  target_link_libraries(descent_test PRIVATE descent GTest::gtest_main)
  target_compile_options(descent_test PRIVATE -Wall -Wextra -Werror)
  include(GoogleTest)
  gtest_discover_tests(descent_test)
endif()
