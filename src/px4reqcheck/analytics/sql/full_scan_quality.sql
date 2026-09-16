SELECT
    "check" AS check_name,
    count(DISTINCT log_id) AS logs_reported,
    sum("count") AS total_findings
FROM quality
GROUP BY "check"
ORDER BY "check";
