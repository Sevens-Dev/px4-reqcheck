#include "descent.hpp"

#include <cstdint>
#include <stdexcept>
#include <vector>

#include <gtest/gtest.h>

namespace {

TEST(LinearPercentile, MatchesNumpyLinearDefinition) {
  std::vector<double> values;
  for (int value = 1; value <= 20; ++value) {
    values.push_back(static_cast<double>(value));
  }
  EXPECT_DOUBLE_EQ(px4reqcheck::linear_percentile(values, 95.0), 19.05);
}

TEST(DescentRate, AppliesTimeAndAltitudeWindows) {
  const px4reqcheck::DescentInput input{
      {0, 1'000'000, 2'000'000, 3'000'000, 4'000'000, 5'000'000, 6'000'000},
      {100.0, 1.0, 2.0, 3.0, 4.0, 50.0, 6.0},
      {-1.0, -1.0, -1.0, -1.0, -1.0, -6.0, -1.0},
      6'000'000,
      5.0,
  };
  const auto result = px4reqcheck::descent_rate_pre_land_p95(input);
  ASSERT_TRUE(result.value.has_value());
  EXPECT_NEAR(*result.value, 5.6, 1e-12);
  EXPECT_FALSE(result.reason.has_value());
}

TEST(DescentRate, ReportsMissingLandingWindow) {
  const px4reqcheck::DescentInput input{{0, 1}, {1.0, 2.0}, {-1.0, -1.0}, std::nullopt, 5.0};
  const auto result = px4reqcheck::descent_rate_pre_land_p95(input);
  EXPECT_FALSE(result.value.has_value());
  ASSERT_TRUE(result.reason.has_value());
  EXPECT_EQ(*result.reason, "window_missing");
}

TEST(Comparator, SupportsAllRequirementOperators) {
  EXPECT_TRUE(px4reqcheck::compare(2.0, ">=", 2.0));
  EXPECT_TRUE(px4reqcheck::compare(2.0, "<=", 2.0));
  EXPECT_TRUE(px4reqcheck::compare(3.0, ">", 2.0));
  EXPECT_TRUE(px4reqcheck::compare(2.0, "<", 3.0));
  EXPECT_THROW(px4reqcheck::compare(2.0, "==", 2.0), std::invalid_argument);
}

}  // namespace
