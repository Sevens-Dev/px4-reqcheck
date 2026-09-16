SELECT
    sw_version,
    count(*) AS log_count,
    avg(duration_s) AS mean_duration_s,
    min(duration_s) AS minimum_duration_s,
    max(duration_s) AS maximum_duration_s
FROM logmeta
GROUP BY sw_version
ORDER BY sw_version;
