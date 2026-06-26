/*
 * 状态判断逻辑：
 * 1. 进程离线：当 NOW() - heartbeat_timestamp > 2分钟 时触发，表示心跳超过2分钟未更新，脚本进程可能已崩溃或被杀死。
 * 2. 优化任务卡死：当心跳正常（NOW() - heartbeat_timestamp ≤ 2分钟）但 NOW() - optimization_timestamp > 15分钟 时触发，表示进程存活但优化主任务（run_optimization_cycle）超过15分钟未执行，可能陷入死循环、死锁或阻塞。
 * 3. 正常：上述两个条件均不满足，表示进程存活且优化任务正常执行。
 *
 * 阈值说明：
 * - 心跳间隔：30秒 → 2分钟约4个心跳周期
 * - 优化周期：5分钟 → 15分钟约3个优化周期
 */
-- 冷却侧
(
    SELECT
        'cooling' AS system,
        hb.heartbeat_timestamp AS last_heartbeat,
        hb.heartbeat_state,
        opt.optimization_timestamp AS last_optimization,
        NOW() - hb.heartbeat_timestamp AS heartbeat_age,
        NOW() - opt.optimization_timestamp AS optimization_age,
        CASE
            WHEN NOW() - hb.heartbeat_timestamp > INTERVAL '2 minutes' THEN '进程离线'
            WHEN NOW() - opt.optimization_timestamp > INTERVAL '15 minutes' THEN '优化任务卡死'
            ELSE '正常'
        END AS status
    FROM cooling_opt_parameters_total hb
    JOIN cooling_opt_parameters_total opt ON hb.id = opt.id
    ORDER BY hb.id DESC

    LIMIT 1
)
UNION ALL
-- 冷冻侧
(
    SELECT
        'chilled' AS system,
        hb.heartbeat_timestamp AS last_heartbeat,
        hb.heartbeat_state,
        opt.optimization_timestamp AS last_optimization,
        NOW() - hb.heartbeat_timestamp AS heartbeat_age,
        NOW() - opt.optimization_timestamp AS optimization_age,
        CASE
            WHEN NOW() - hb.heartbeat_timestamp > INTERVAL '2 minutes' THEN '进程离线'
            WHEN NOW() - opt.optimization_timestamp > INTERVAL '15 minutes' THEN '优化任务卡死'
            ELSE '正常'
        END AS status
    FROM chilled_opt_parameters_total hb
    JOIN chilled_opt_parameters_total opt ON hb.id = opt.id
    ORDER BY hb.id DESC
    LIMIT 1
);
