SELECT
    name,
    count(DISTINCT log_id) AS log_count,
    min(value_num) AS minimum,
    max(value_num) AS maximum
FROM parameters
GROUP BY name
ORDER BY log_count DESC, name;
