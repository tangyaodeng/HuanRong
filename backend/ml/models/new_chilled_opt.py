"""
new_chilled_opt.py — 冷冻水优化调度器（薄子类）
=============================================
继承 BaseOptimizationScheduler，仅包含冷冻水特有的逻辑：
  - 直接从 DB 配置读取约束（无湿球温度驱动）
  - 回水 > 供水，温差范围过滤在生对阶段完成
  - 主机+冷冻泵两组功率聚合
  - chilled_opt_parameters_total 表读写

使用方式（与旧 chilled_opt.py 完全兼容）：
    from ml.models.new_chilled_opt import ChilledTempSchedulerTotal, main
    scheduler = ChilledTempSchedulerTotal()
    scheduler.start()
"""
import sys, os
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.config import settings
from ml.models.base_optimizer import BaseOptimizationScheduler
import json
import random
import xgboost as xgb

logger = logging.getLogger("ChilledTempSchedulerTotal")


class ChilledTempSchedulerTotal(BaseOptimizationScheduler):
    """冷冻水系统优化调度器（总功率模型版本，增强残差修正）"""
    OPT_TYPE = "chilled"

    # ======================== 约束条件（直接使用 DB 配置）========================
    def _get_optimization_constraints(self, base_values: Dict) -> Optional[Dict]:
        if self.optimization_config is None:
            self.logger.error("优化配置未加载")
            return None
        return {
            'supply_temp_lower_limit': self.optimization_config['supply_temp_lower_limit'],
            'supply_temp_upper_limit': self.optimization_config['supply_temp_upper_limit'],
            'return_temp_lower_limit': self.optimization_config['return_temp_lower_limit'],
            'return_temp_upper_limit': self.optimization_config['return_temp_upper_limit'],
            'temp_diff_lower_limit': self.optimization_config['temp_diff_lower_limit'],
            'temp_diff_upper_limit': self.optimization_config['temp_diff_upper_limit'],
            'step_size': self.STEP_SIZE,
        }

    # ======================== 温度对生成（回水>供水，温差在生对时过滤）========================
    def _generate_temperature_pairs(self, constraints: Dict) -> List[Tuple[float, float]]:
        if constraints is None:
            return []
        in_min = constraints['supply_temp_lower_limit']
        in_max = constraints['supply_temp_upper_limit']
        ret_min = constraints['return_temp_lower_limit']
        ret_max = constraints['return_temp_upper_limit']
        d_min = constraints['temp_diff_lower_limit']
        d_max = constraints['temp_diff_upper_limit']
        inlets = np.arange(in_min, in_max + self.STEP_SIZE, self.STEP_SIZE).round(1).tolist()
        returns = np.arange(ret_min, ret_max + self.STEP_SIZE, self.STEP_SIZE).round(1).tolist()
        pairs = [(i, r) for i in inlets for r in returns if r > i and d_min <= (r - i) <= d_max]
        self.logger.info(f"生成 {len(pairs)} 个温度组合 (inlet>{len(inlets)}档, return>{len(returns)}档, delta={d_min}~{d_max})")
        return pairs

    # ======================== 单次预测 ========================
    def _predict_for_temp_pair(self, inlet_temp, return_temp, base_values, historical_residuals):
        host_feat = self.prepare_features(base_values.copy(), inlet_temp, return_temp, 'host_0')
        # 找到第一个 chilled_pump 的 key
        pump_key = next((k for k in self.model_keys if self.group_for_key[k] == 'chilled_pump'), None)
        if pump_key is None:
            return None
        pump_feat = self.prepare_features(base_values.copy(), inlet_temp, return_temp, pump_key)
        if host_feat is None or pump_feat is None:
            return None

        host_pwr = self.predict_power_with_status(
            'host_0', host_feat, base_values, inlet_temp, return_temp,
            historical_residuals=historical_residuals.get('host_0') if historical_residuals else None,
        )
        pump_pwr = self.predict_power_with_status(
            pump_key, pump_feat, base_values, inlet_temp, return_temp,
            historical_residuals=historical_residuals.get(pump_key) if historical_residuals else None,
        )
        total = host_pwr + pump_pwr
        cur_total = self._get_current_total_power(base_values)

        return {
            'inlet': inlet_temp,
            'return': return_temp,
            'host_power': round(host_pwr, 2),
            'pump_power': round(pump_pwr, 2),
            'total_power': round(total, 2),
            'power_diff': round(total - cur_total, 2),
            'power_diff_percent': round((total - cur_total) / cur_total * 100, 2) if cur_total else 0,
        }

    # ======================== 最终结果包装 ========================
    def _build_final_result(self, best, all_results, constraints, base_values, cur_total):
        cur_inlet_pt = self._resolve_attr(self._temp_inlet_attr)
        cur_return_pt = self._resolve_attr(self._temp_return_attr)
        cur_inlet = base_values.get(cur_inlet_pt, 7.0)
        cur_return = base_values.get(cur_return_pt, 12.0)
        cur_host = self._get_group_total_power(base_values, 'host')
        cur_pump = self._get_group_total_power(base_values, 'chilled_pump')
        host_run = any(base_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('host', []))
        pump_run = any(base_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('chilled_pump', []))

        return {
            'success': True,
            'optimal': best,
            'all_results': all_results,
            'constraints': constraints,
            'current': {
                'inlet': round(cur_inlet, 1),
                'return': round(cur_return, 1),
                'host_power': round(cur_host, 2),
                'pump_power': round(cur_pump, 2),
                'total_power': round(cur_total, 2),
                'host_run': host_run,
                'pump_run': pump_run,
            },
        }

    # ======================== 回退结果 ========================
    def _create_fallback_result(self, feature_values):
        cur_inlet_pt = self._resolve_attr(self._temp_inlet_attr)
        cur_return_pt = self._resolve_attr(self._temp_return_attr)
        inlet = feature_values.get(cur_inlet_pt, 7.0)
        ret = feature_values.get(cur_return_pt, 12.0)
        host = self._get_group_total_power(feature_values, 'host')
        pump = self._get_group_total_power(feature_values, 'chilled_pump')
        host_run = any(feature_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('host', []))
        pump_run = any(feature_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('chilled_pump', []))

        return {
            'optimal': {
                'inlet': round(inlet, 1), 'return': round(ret, 1),
                'host_power': round(host, 2), 'pump_power': round(pump, 2),
                'total_power': round(host + pump, 2),
                'power_diff': 0, 'power_diff_percent': 0,
            },
            'all_results': [],
            'constraints': self.optimization_config or {},
            'current': {
                'inlet': round(inlet, 1), 'return': round(ret, 1),
                'host_power': round(host, 2), 'pump_power': round(pump, 2),
                'total_power': round(host + pump, 2),
                'host_run': host_run, 'pump_run': pump_run,
            },
            'is_valid': False,
        }

    # ======================== 保存结果 ========================
    def _save_results(self, opt_result, data_time) -> bool:
        try:
            if not self.postgres_engine:
                return False
            opt = opt_result['optimal']
            cur = opt_result['current']
            cfg = opt_result.get('constraints', self.optimization_config) or {}

            supply_applied = opt_result.get('optimized_supply_temp_applied', False)
            diff_applied = opt_result.get('optimized_temp_diff_applied', False)
            fail_list = opt_result.get('failure_reasons', [])
            fail_str = '; '.join(f"{i+1}. {r}" for i, r in enumerate(fail_list)) if fail_list else None

            diff_total = opt['total_power'] - cur['total_power']
            diff_host = opt['host_power'] - cur['host_power']
            diff_pump = opt['pump_power'] - cur['pump_power']
            diff_supply = opt['inlet'] - cur['inlet']
            diff_return = opt['return'] - cur['return']
            diff_delta = (opt['return'] - opt['inlet']) - (cur['return'] - cur['inlet'])

            pct_total = -diff_total / cur['total_power'] * 100 if cur['total_power'] else 0
            pct_host = -diff_host / cur['host_power'] * 100 if cur['host_power'] else 0
            pct_pump = -diff_pump / cur['pump_power'] * 100 if cur['pump_power'] else 0

            now = datetime.now()
            if isinstance(data_time, datetime):
                dt_obj = data_time
                dt_str = data_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                try:
                    dt_obj = datetime.strptime(str(data_time), '%Y-%m-%d %H:%M:%S')
                    dt_str = str(data_time)
                except Exception:
                    dt_obj = now
                    dt_str = now.strftime('%Y-%m-%d %H:%M:%S')
            time_diff = (now - dt_obj).total_seconds() / 60

            remarks_parts = [
                f"数据时间: {dt_str}",
                f"主机{'运行' if cur.get('host_run') else '停止'}",
                f"冷冻泵{'运行' if cur.get('pump_run') else '停止'}",
            ]
            if time_diff > self.data_recency_minutes:
                remarks_parts.append(f"数据超时({time_diff:.1f}分钟)")
            if not opt_result.get('is_valid', True):
                remarks_parts.append("优化失败(使用当前值)")
            # 将失败原因写入 remarks 便于运维快速定位
            if fail_list:
                short = fail_list[:2]
                remarks_parts.append(f"原因: {'; '.join(short)}")
            remarks = ", ".join(remarks_parts)

            query = """
            INSERT INTO chilled_opt_parameters_total (
                return_temp_lower_limit, return_temp_upper_limit,
                supply_temp_lower_limit, supply_temp_upper_limit,
                temp_diff_lower_limit, temp_diff_upper_limit,
                current_total_power, current_host_total_power, current_chilled_pump_total_power,
                current_supply_temp, current_return_temp, current_temp_diff,
                optimized_total_power, optimized_host_total_power, optimized_chilled_pump_total_power,
                optimized_supply_temp, optimized_return_temp, optimized_temp_diff,
                diff_total_power, diff_host_total_power, diff_chilled_pump_total_power,
                diff_supply_temp, diff_return_temp, diff_temp_diff,
                percent_total_power, percent_host_total_power, percent_chilled_pump_total_power,
                total_energy_saving, energy_saving_percent,
                optimized_supply_temp_applied, optimized_temp_diff_applied, failure_reasons,
                remarks
            ) VALUES (
                :r_low, :r_up, :s_low, :s_up, :d_low, :d_up,
                :cur_total, :cur_host, :cur_pump,
                :cur_supply, :cur_return, :cur_delta,
                :opt_total, :opt_host, :opt_pump,
                :opt_supply, :opt_return, :opt_delta,
                :diff_total, :diff_host, :diff_pump,
                :diff_supply, :diff_return, :diff_delta,
                :pct_total, :pct_host, :pct_pump,
                :save_total, :save_pct,
                :sup_app, :diff_app, :fail_reasons, :remarks
            )
            """
            params = {
                'r_low': float(cfg.get('return_temp_lower_limit', 0)),
                'r_up': float(cfg.get('return_temp_upper_limit', 0)),
                's_low': float(cfg.get('supply_temp_lower_limit', 0)),
                's_up': float(cfg.get('supply_temp_upper_limit', 0)),
                'd_low': float(cfg.get('temp_diff_lower_limit', 0)),
                'd_up': float(cfg.get('temp_diff_upper_limit', 0)),
                'cur_total': float(cur['total_power']),
                'cur_host': float(cur['host_power']),
                'cur_pump': float(cur['pump_power']),
                'cur_supply': float(cur['inlet']),
                'cur_return': float(cur['return']),
                'cur_delta': float(cur['return'] - cur['inlet']),
                'opt_total': float(opt['total_power']),
                'opt_host': float(opt['host_power']),
                'opt_pump': float(opt['pump_power']),
                'opt_supply': float(opt['inlet']),
                'opt_return': float(opt['return']),
                'opt_delta': float(opt['return'] - opt['inlet']),
                'diff_total': float(diff_total), 'diff_host': float(diff_host),
                'diff_pump': float(diff_pump),
                'diff_supply': float(diff_supply), 'diff_return': float(diff_return),
                'diff_delta': float(diff_delta),
                'pct_total': float(pct_total), 'pct_host': float(pct_host),
                'pct_pump': float(pct_pump),
                'save_total': float(-diff_total), 'save_pct': float(pct_total),
                'sup_app': supply_applied, 'diff_app': diff_applied,
                'fail_reasons': fail_str, 'remarks': remarks,
            }
            with self.postgres_engine.connect() as c:
                c.execute(text(query), params)
                c.commit()
            self.logger.info(f"结果已保存到 chilled_opt_parameters_total, 下发标记: 供水={supply_applied}, 温差={diff_applied}")
            return True
        except Exception as e:
            self.logger.error(f"保存失败: {e}")
            import traceback; traceback.print_exc()
            return False

    # ======================== Redis 缓存 ========================
    def _cache_to_redis(self, opt_result):
        if self.redis_client is None:
            return
        try:
            all_res = opt_result.get('all_results', [])
            if not all_res:
                return
            best = opt_result['optimal']
            desc = sorted(all_res, key=lambda x: x['total_power'], reverse=True)
            others = [r for r in desc if not (
                r['total_power'] == best['total_power'] and
                r['inlet'] == best['inlet'] and
                r['return'] == best['return']
            )]
            if len(desc) <= 20:
                selected = desc
            else:
                sz = min(19, len(others))
                so = random.sample(others, sz) if sz > 0 else []
                selected = so + [best]
                selected.sort(key=lambda x: x['total_power'], reverse=True)
            combos = []
            for idx, r in enumerate(selected):
                orig_rank = next((i+1 for i, c in enumerate(desc)
                                  if c['total_power']==r['total_power']
                                  and c['inlet']==r['inlet']
                                  and c['return']==r['return']), idx+1)
                combos.append({
                    "index": orig_rank,
                    "chilled_inlet_temp": r['inlet'],
                    "chilled_return_temp": r['return'],
                    "actual_inlet_temp": r['inlet'],
                    "actual_return_temp": r['return'],
                    "delta_temp": round(r['return'] - r['inlet'], 1),
                    "host_power": r['host_power'],
                    "pump_power": r['pump_power'],
                    "total_power": r['total_power'],
                    "power_diff": r['power_diff'],
                    "power_diff_percent": r['power_diff_percent'],
                })
            cache = {"timestamp": datetime.now().isoformat(), "combinations": combos}
            key = self.opt_cfg["redis_key_pattern"].format(program_name=settings.PROGRAM_NAME)
            self.redis_client.setex(key, 300, json.dumps(cache, ensure_ascii=False))
            self.logger.info(f"Redis 缓存 {len(combos)} 个组合 -> {key}")
        except Exception as e:
            self.logger.error(f"Redis 缓存失败: {e}")

    # ======================== 调度器入口（向后兼容）========================
    def start(self):
        """启动（兼容旧版 API）"""
        return self.start_scheduler()

    def stop(self):
        """停止（兼容旧版 API）"""
        return self.stop_scheduler()

    def run_cycle(self):
        """运行一次（兼容旧版 API）"""
        return self.run_optimization_cycle()


def main():
    scheduler = ChilledTempSchedulerTotal()
    scheduler.start()


if __name__ == "__main__":
    main()
