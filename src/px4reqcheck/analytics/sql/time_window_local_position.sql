WITH starts AS (
    SELECT log_id, min("timestamp") AS start_us
    FROM local_position
    GROUP BY log_id
)
SELECT
    samples.log_id,
    count(*) AS samples_in_window,
    avg(samples.z) AS mean_z_m
FROM local_position AS samples
JOIN starts USING (log_id)
WHERE samples."timestamp" >= starts.start_us + 10000000
  AND samples."timestamp" < starts.start_us + 20000000
GROUP BY samples.log_id
ORDER BY samples.log_id;
