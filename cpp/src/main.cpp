#include "descent.hpp"

#include <cstdint>
#include <limits>
#include <fstream>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace {

using json = nlohmann::json;

std::vector<double> nullable_doubles(const json& values) {
  std::vector<double> result;
  result.reserve(values.size());
  for (const auto& value : values) {
    result.push_back(value.is_null() ? std::numeric_limits<double>::quiet_NaN()
                                     : value.get<double>());
  }
  return result;
}

px4reqcheck::MetricResult descent_from_json(const json& raw) {
  if (!raw.at("reason").is_null()) {
    return {std::nullopt, raw.at("reason").get<std::string>()};
  }
  px4reqcheck::DescentInput input{
      raw.at("timestamps_us").get<std::vector<std::int64_t>>(),
      nullable_doubles(raw.at("descent_vz")),
      nullable_doubles(raw.at("z_m")),
      std::nullopt,
      raw.at("land_alt2_m").get<double>(),
  };
  if (!raw.at("land_edge_us").is_null()) {
    input.land_edge_us = raw.at("land_edge_us").get<std::int64_t>();
  }
  return px4reqcheck::descent_rate_pre_land_p95(input);
}

json evaluate(const json& document) {
  json output = json::array();
  for (const auto& log : document.at("logs")) {
    const auto& metrics = log.at("metrics");
    const auto& reasons = log.at("metric_reasons");
    for (const auto& threshold : log.at("thresholds")) {
      const std::string metric_name = threshold.at("metric").get<std::string>();
      json verdict{{"log_id", log.at("log_id")},
                   {"req_id", threshold.at("req_id")},
                   {"metric_value", nullptr}};
      if (!threshold.at("reason").is_null()) {
        verdict["status"] = "not_evaluable";
        verdict["reason"] = threshold.at("reason");
        output.push_back(std::move(verdict));
        continue;
      }

      px4reqcheck::MetricResult metric{std::nullopt, std::nullopt};
      if (metric_name == "descent_rate_pre_land_p95") {
        metric = descent_from_json(log.at("raw"));
      } else if (!metrics.at(metric_name).is_null()) {
        metric.value = metrics.at(metric_name).get<double>();
      } else {
        metric.reason = reasons.at(metric_name).get<std::string>();
      }

      verdict["metric_value"] = metric.value.has_value() ? json(*metric.value) : json(nullptr);
      if (metric.reason.has_value()) {
        verdict["status"] = "not_evaluable";
        verdict["reason"] = *metric.reason;
      } else if (!metric.value.has_value() || threshold.at("value").is_null()) {
        throw std::runtime_error("resolved check is missing a metric or threshold");
      } else {
        const bool passed = px4reqcheck::compare(*metric.value,
                                                 threshold.at("comparator").get<std::string>(),
                                                 threshold.at("value").get<double>());
        verdict["status"] = passed ? "pass" : "fail";
        verdict["reason"] = nullptr;
      }
      output.push_back(std::move(verdict));
    }
  }
  return output;
}

}  // namespace

int main(const int argc, char* argv[]) {
  try {
    if (argc != 3) {
      std::cerr << "usage: px4-reqcheck-cpp CHECKS_JSON VERDICTS_JSON\n";
      return 2;
    }
    std::ifstream input(argv[1]);
    if (!input) {
      throw std::runtime_error("cannot open checks input");
    }
    json document;
    input >> document;
    if (document.at("version") != 1) {
      throw std::runtime_error("unsupported checks contract version");
    }
    std::ofstream output(argv[2]);
    if (!output) {
      throw std::runtime_error("cannot open verdict output");
    }
    output << evaluate(document).dump(2) << '\n';
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  return 0;
}
