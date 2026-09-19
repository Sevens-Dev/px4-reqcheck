execute_process(
  COMMAND "${CHECKER}" "${INPUT}" "${OUTPUT}"
  RESULT_VARIABLE result
  ERROR_VARIABLE error
)
if(NOT result EQUAL 0)
  message(FATAL_ERROR "checker failed: ${error}")
endif()
file(READ "${OUTPUT}" verdicts)
string(JSON count LENGTH "${verdicts}")
string(JSON battery_status GET "${verdicts}" 0 status)
string(JSON descent_status GET "${verdicts}" 1 status)
string(JSON descent_value GET "${verdicts}" 1 metric_value)
if(NOT count EQUAL 2 OR NOT battery_status STREQUAL "pass" OR NOT descent_status STREQUAL "pass")
  message(FATAL_ERROR "unexpected checker verdicts: ${verdicts}")
endif()
if(descent_value LESS 5.599999 OR descent_value GREATER 5.600001)
  message(FATAL_ERROR "C++ checker reused the scalar metric instead of deriving 5.6: ${descent_value}")
endif()
