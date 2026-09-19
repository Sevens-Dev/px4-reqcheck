SELECT
    "check" AS check_name,
    count(DISTINCT CASE WHEN "count" > 0 THEN log_id END) AS logs_reported,
    sum("count") AS total_findings
FROM quality
GROUP BY "check"
ORDER BY "check";
