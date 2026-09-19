#include "descent.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace px4reqcheck {

double linear_percentile(std::vector<double> values, const double percentile) {
  if (values.empty()) {
    throw std::invalid_argument("percentile requires at least one value");
  }
  if (percentile < 0.0 || percentile > 100.0) {
    throw std::invalid_argument("percentile must be between 0 and 100");
  }
  std::sort(values.begin(), values.end());
  const double position = (static_cast<double>(values.size()) - 1.0) * percentile / 100.0;
  const auto lower = static_cast<std::size_t>(std::floor(position));
  const auto upper = static_cast<std::size_t>(std::ceil(position));
  const double fraction = position - static_cast<double>(lower);
  return values[lower] + fraction * (values[upper] - values[lower]);
}

MetricResult descent_rate_pre_land_p95(const DescentInput& input) {
  if (!input.land_edge_us.has_value()) {
    return {std::nullopt, "window_missing"};
  }
  if (input.timestamps_us.size() != input.vz_m_s.size() ||
      input.timestamps_us.size() != input.z_m.size()) {
    throw std::invalid_argument("descent arrays must have equal length");
  }

  std::vector<double> selected;
  const auto window_start = *input.land_edge_us - 5'000'000;
  for (std::size_t index = 0; index < input.timestamps_us.size(); ++index) {
    const auto timestamp = input.timestamps_us[index];
    const double vz = input.vz_m_s[index];
    const double z = input.z_m[index];
    if (timestamp >= window_start && timestamp <= *input.land_edge_us &&
        -z < input.land_alt2_m && std::isfinite(vz) && std::isfinite(z)) {
      selected.push_back(vz);
    }
  }
  if (selected.size() < 2) {
    return {std::nullopt, "insufficient_samples"};
  }
  return {linear_percentile(std::move(selected), 95.0), std::nullopt};
}

bool compare(const double metric, const std::string& comparator, const double threshold) {
  if (comparator == ">=") {
    return metric >= threshold;
  }
  if (comparator == "<=") {
    return metric <= threshold;
  }
  if (comparator == ">") {
    return metric > threshold;
  }
  if (comparator == "<") {
    return metric < threshold;
  }
  throw std::invalid_argument("unsupported comparator: " + comparator);
}

}  // namespace px4reqcheck
