#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace px4reqcheck {

struct MetricResult {
  std::optional<double> value;
  std::optional<std::string> reason;
};

struct DescentInput {
  std::vector<std::int64_t> timestamps_us;
  std::vector<double> vz_m_s;
  std::vector<double> z_m;
  std::optional<std::int64_t> land_edge_us;
  double land_alt2_m;
};

double linear_percentile(std::vector<double> values, double percentile);
MetricResult descent_rate_pre_land_p95(const DescentInput& input);
bool compare(double metric, const std::string& comparator, double threshold);

}  // namespace px4reqcheck
