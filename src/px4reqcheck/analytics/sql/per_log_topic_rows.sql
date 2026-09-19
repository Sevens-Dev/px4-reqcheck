SELECT
    log_id,
    sum(row_count) AS telemetry_rows,
    count(*) AS topic_count
FROM topic_inventory
GROUP BY log_id
ORDER BY log_id;
