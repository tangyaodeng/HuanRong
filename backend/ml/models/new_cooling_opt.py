"""
new_cooling_opt.py — 冷却水优化调度器（薄子类）
=============================================
继承 BaseOptimizationScheduler，仅包含冷却水特有的逻辑：
  - 湿球温度驱动的约束条件
  - 散热量过滤
  - 主机+冷却塔+冷却泵三组功率聚合
  - cooling_opt_parameters_total 表读写

使用方式（与旧 cooling_opt.py 完全兼容）：
    from ml.models.new_cooling_opt import CoolingTempSchedulerTotal, main
    scheduler = CoolingTempSchedulerTotal()
    scheduler.start_scheduler()
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

logger = logging.getLogger("CoolingTempSchedulerTotal")


class CoolingTempSchedulerTotal(BaseOptimizationScheduler):
    """冷却水系统优化调度器（总功率模型版本，直接修正模式）"""
    OPT_TYPE = "cooling"

    # ======================== 约束条件 ========================
    def _get_optimization_constraints(self, base_values: Dict) -> Optional[Dict]:
        if self.optimization_config is None:
            self.logger.error("优化配置未加载")
            return None
        wet_bulb = base_values.get(self._resolve_attr("wet_bulb_temperature"), 20.0)
        return_lower = self.optimization_config['return_temp_lower_limit']
        supply_lower = self.optimization_config['supply_temp_lower_limit']
        tmin_return = wet_bulb + return_lower
        tmin_supply = wet_bulb + supply_lower
        return {
            'wet_bulb_temp': round(wet_bulb, 1),
            'Tmin_return': round(tmin_return, 1),
            'Tmin_supply': round(tmin_supply, 1),
            'inlet_min': round(max(tmin_supply, wet_bulb + 1), 1),
            'inlet_max': round(self.optimization_config['supply_temp_upper_limit'], 1),
            'return_min': round(max(tmin_return, wet_bulb + 1), 1),
            'return_max': round(self.optimization_config['return_temp_upper_limit'], 1),
            'delta_temp_min': self.optimization_config['temp_diff_lower_limit'],
            'delta_temp_max': self.optimization_config['temp_diff_upper_limit'],
            'step_size': self.STEP_SIZE,
            'heat_dissipation_lower_limit': self.optimization_config['heat_dissipation_lower_limit'],
            'heat_dissipation_upper_limit': self.optimization_config['heat_dissipation_upper_limit'],
        }

    # ======================== 温度对生成 ========================
    def _generate_temperature_pairs(self, constraints: Dict) -> List[Tuple[float, float]]:
        if constraints is None:
            return []
        inlets = np.arange(constraints['inlet_min'], constraints['inlet_max'] + self.STEP_SIZE, self.STEP_SIZE)
        inlets = [round(t, 1) for t in inlets]
        returns = np.arange(constraints['return_min'], constraints['return_max'] + self.STEP_SIZE, self.STEP_SIZE)
        returns = [round(t, 1) for t in returns]
        pairs = [(i, r) for i in inlets for r in returns if i > r]
        self.logger.info(f"生成 {len(pairs)} 个温度组合 (inlet>{len(inlets)}档, return>{len(returns)}档)")
        return pairs

    # ======================== 单次预测 ========================
    def _predict_for_temp_pair(self, inlet_temp, return_temp, base_values, historical_residuals):
        sub_powers = {}
        for mk in self.model_keys:
            feat = self.prepare_features(base_values.copy(), inlet_temp, return_temp, mk)
            if feat is None:
                return None
            pred = self.predict_power_with_status(
                mk, feat, base_values, inlet_temp, return_temp,
                historical_residuals=historical_residuals.get(mk) if historical_residuals else None,
            )
            sub_powers[mk] = pred

        # 总功率（三组合计）
        total = sum(sub_powers[k] for k in sub_powers if self.group_for_key[k] in self._device_groups)
        host_pwr = sum(sub_powers[k] for k in sub_powers if self.group_for_key[k] == 'host')

        # 散热量检查
        cur_heat = base_values.get(self._resolve_attr("composite_system_heat_dissipation_1"), 2000.0)
        cur_cool_cap = base_values.get(self._resolve_attr("cooling_capacity_of_the_cooling_side_of_host_1"), 1000.0)
        heat = host_pwr + cur_cool_cap
        min_heat = self.optimization_config.get('heat_dissipation_lower_limit', 0.8) * cur_heat
        max_heat = self.optimization_config.get('heat_dissipation_upper_limit', 1.2) * cur_heat

        skip_reason = None
        delta = inlet_temp - return_temp
        if delta < self.optimization_config.get('temp_diff_lower_limit', 0):
            skip_reason = 'delta_low'
        elif delta > self.optimization_config.get('temp_diff_upper_limit', 99):
            skip_reason = 'delta_high'
        elif inlet_temp < self.optimization_config.get('supply_temp_lower_limit', -99):
            skip_reason = 'inlet_low'
        elif inlet_temp > self.optimization_config.get('supply_temp_upper_limit', 99):
            skip_reason = 'inlet_high'
        elif return_temp < self.optimization_config.get('return_temp_lower_limit', -99):
            skip_reason = 'return_low'
        elif return_temp > self.optimization_config.get('return_temp_upper_limit', 99):
            skip_reason = 'return_high'
        elif heat < min_heat:
            skip_reason = 'heat_low'
        elif heat > max_heat:
            skip_reason = 'heat_high'

        cur_total = self._get_current_total_power(base_values)
        cur_inlet_pt = self._resolve_attr(self._temp_inlet_attr)
        cur_return_pt = self._resolve_attr(self._temp_return_attr)
        cur_inlet = base_values.get(cur_inlet_pt, 32.0)
        cur_return = base_values.get(cur_return_pt, 28.0)

        entry = {
            'cooling_inlet_temp': inlet_temp,
            'cooling_return_temp': return_temp,
            'actual_inlet_temp': round(inlet_temp, 1),
            'actual_return_temp': round(return_temp, 1),
            'delta_temp': round(delta, 1),
            'host_power': round(sum(sub_powers[k] for k in sub_powers if self.group_for_key[k] == 'host'), 2),
            'cooling_pump_power': round(sum(sub_powers[k] for k in sub_powers if self.group_for_key[k] == 'cooling_pump'), 2),
            'cooling_tower_power': round(sum(sub_powers[k] for k in sub_powers if self.group_for_key[k] == 'cooling_tower'), 2),
            'total_power': round(total, 2),
            'system_heat_dissipation': round(heat, 2),
            'heat_dissipation_percent': round(heat / cur_heat * 100, 1) if cur_heat else 100.0,
            'power_diff': round(total - cur_total, 2),
            'power_diff_percent': round((total - cur_total) / cur_total * 100, 2) if cur_total else 0,
            'inlet_temp_diff': round(abs(inlet_temp - cur_inlet), 1),
            'return_temp_diff': round(abs(return_temp - cur_return), 1),
            'sub_powers': {k: round(v, 2) for k, v in sub_powers.items()},
        }
        if skip_reason:
            entry['__skip_reason'] = skip_reason
        return entry

    # ======================== 最终结果包装 ========================
    def _build_final_result(self, best, all_results, constraints, base_values, cur_total):
        cur_inlet_pt = self._resolve_attr(self._temp_inlet_attr)
        cur_return_pt = self._resolve_attr(self._temp_return_attr)
        cur_heat_1 = base_values.get(self._resolve_attr("composite_system_heat_dissipation_1"), 2000.0)
        cur_cool_cap = base_values.get(self._resolve_attr("cooling_capacity_of_the_cooling_side_of_host_1"), 1000.0)
        cur_inlet = base_values.get(cur_inlet_pt, 32.0)
        cur_return = base_values.get(cur_return_pt, 28.0)

        host_run = any(base_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('host', []))
        pump_run = any(base_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('cooling_pump', []))
        tower_run = any(base_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('cooling_tower', []))

        return {
            'success': True,
            'optimal_result': best,
            'all_valid_results': all_results[:10],
            'all_results': all_results,
            'constraints': constraints,
            'current_values': {
                'cooling_inlet_temp': round(cur_inlet, 1),
                'cooling_return_temp': round(cur_return, 1),
                'system_heat_dissipation': round(cur_heat_1, 2),
                'instant_cooling_capacity': round(cur_cool_cap, 2),
                'host_power': round(self._get_group_total_power(base_values, 'host'), 2),
                'cooling_pump_power': round(self._get_group_total_power(base_values, 'cooling_pump'), 2),
                'cooling_tower_power': round(self._get_group_total_power(base_values, 'cooling_tower'), 2),
                'total_power': round(cur_total, 2),
                'host_running': host_run,
                'pump_running': pump_run,
                'tower_running': tower_run,
            },
            'total_candidates': len(all_results),
            'optimization_config': self.optimization_config,
        }

    # ======================== 回退结果 ========================
    def _create_fallback_result(self, feature_values):
        cur_inlet_pt = self._resolve_attr(self._temp_inlet_attr)
        cur_return_pt = self._resolve_attr(self._temp_return_attr)
        cur_heat_1 = feature_values.get(self._resolve_attr("composite_system_heat_dissipation_1"), 2000.0)
        cur_cool_cap = feature_values.get(self._resolve_attr("cooling_capacity_of_the_cooling_side_of_host_1"), 1000.0)
        cur_inlet = feature_values.get(cur_inlet_pt, 32.0)
        cur_return = feature_values.get(cur_return_pt, 28.0)

        host = self._get_group_total_power(feature_values, 'host')
        pump = self._get_group_total_power(feature_values, 'cooling_pump')
        tower = self._get_group_total_power(feature_values, 'cooling_tower')
        total = host + pump + tower

        host_run = any(feature_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('host', []))
        pump_run = any(feature_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('cooling_pump', []))
        tower_run = any(feature_values.get(pt, 0) == 1.0 for pt in self.group_status_points.get('cooling_tower', []))

        return {
            'optimal_result': {
                'cooling_inlet_temp': cur_inlet, 'cooling_return_temp': cur_return,
                'actual_inlet_temp': round(cur_inlet, 1), 'actual_return_temp': round(cur_return, 1),
                'delta_temp': round(cur_inlet - cur_return, 1),
                'host_power': round(host, 2), 'cooling_pump_power': round(pump, 2),
                'cooling_tower_power': round(tower, 2), 'total_power': round(total, 2),
                'system_heat_dissipation': round(cur_heat_1, 2), 'heat_dissipation_percent': 100.0,
                'power_diff': 0.0, 'power_diff_percent': 0.0,
                'inlet_temp_diff': 0.0, 'return_temp_diff': 0.0,
                'host_running': host_run, 'pump_running': pump_run, 'tower_running': tower_run,
                'is_valid': False,
            },
            'all_valid_results': [], 'all_results': [],
            'constraints': None,
            'current_values': {
                'cooling_inlet_temp': round(cur_inlet, 1), 'cooling_return_temp': round(cur_return, 1),
                'system_heat_dissipation': round(cur_heat_1, 2),
                'instant_cooling_capacity': round(cur_cool_cap, 2),
                'host_power': round(host, 2), 'cooling_pump_power': round(pump, 2),
                'cooling_tower_power': round(tower, 2), 'total_power': round(total, 2),
                'host_running': host_run, 'pump_running': pump_run, 'tower_running': tower_run,
            },
            'total_candidates': 0,
            'optimization_config': self.optimization_config,
        }

    # ======================== 保存结果 ========================
    def _save_results(self, opt_result, data_time) -> bool:
        try:
            if not self.postgres_engine:
                return False
            opt = opt_result['optimal_result']
            cur = opt_result['current_values']
            cfg = opt_result.get('optimization_config', self.optimization_config) or {}

            return_applied = opt_result.get('optimized_return_temp_applied', False)
            diff_applied = opt_result.get('optimized_temp_diff_applied', False)
            fail_list = opt_result.get('failure_reasons', [])
            fail_str = '; '.join(f"{i+1}. {r}" for i, r in enumerate(fail_list)) if fail_list else None

            diff_total = opt['total_power'] - cur['total_power']
            diff_host = opt['host_power'] - cur['host_power']
            diff_tower = opt['cooling_tower_power'] - cur['cooling_tower_power']
            diff_pump = opt['cooling_pump_power'] - cur['cooling_pump_power']
            diff_supply = opt['actual_inlet_temp'] - cur['cooling_inlet_temp']
            diff_return = opt['actual_return_temp'] - cur['cooling_return_temp']
            diff_delta = opt['delta_temp'] - (cur['cooling_inlet_temp'] - cur['cooling_return_temp'])

            pct_total = -diff_total / cur['total_power'] * 100 if cur['total_power'] else 0
            pct_host = -diff_host / cur['host_power'] * 100 if cur['host_power'] else 0
            pct_tower = -diff_tower / cur['cooling_tower_power'] * 100 if cur['cooling_tower_power'] else 0
            pct_pump = -diff_pump / cur['cooling_pump_power'] * 100 if cur['cooling_pump_power'] else 0

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
                f"主机{'运行' if cur.get('host_running') else '停止'}",
                f"冷却泵{'运行' if cur.get('pump_running') else '停止'}",
                f"冷却塔{'运行' if cur.get('tower_running') else '停止'}",
            ]
            if time_diff > self.data_recency_minutes:
                remarks_parts.append(f"数据超时({time_diff:.1f}分钟)")
            if not opt.get('is_valid', True):
                remarks_parts.append("优化失败(使用当前值)")
            # 将失败原因写入 remarks 便于运维快速定位
            if fail_list:
                short = fail_list[:2]
                remarks_parts.append(f"原因: {'; '.join(short)}")
            remarks = ", ".join(remarks_parts)

            query = """
            INSERT INTO cooling_opt_parameters_total (
                return_temp_lower_limit, return_temp_upper_limit,
                supply_temp_lower_limit, supply_temp_upper_limit,
                temp_diff_lower_limit, temp_diff_upper_limit,
                heat_dissipation_lower_limit, heat_dissipation_upper_limit,
                current_total_power, current_host_total_power,
                current_cooling_tower_total_power, current_cooling_pump_total_power,
                current_supply_temp, current_return_temp, current_temp_diff,
                current_heat_dissipation,
                optimized_total_power, optimized_host_total_power,
                optimized_cooling_tower_total_power, optimized_cooling_pump_total_power,
                optimized_supply_temp, optimized_return_temp, optimized_temp_diff,
                optimized_heat_dissipation,
                diff_total_power, diff_host_total_power,
                diff_cooling_tower_total_power, diff_cooling_pump_total_power,
                diff_supply_temp, diff_return_temp, diff_temp_diff,
                diff_heat_dissipation,
                percent_total_power, percent_host_total_power,
                percent_cooling_tower_total_power, percent_cooling_pump_total_power,
                total_energy_saving, energy_saving_percent,
                optimized_return_temp_applied, optimized_temp_diff_applied,
                failure_reasons, remarks
            ) VALUES (
                :r_low, :r_up, :s_low, :s_up, :d_low, :d_up,
                :h_low, :h_up,
                :cur_total, :cur_host, :cur_tower, :cur_pump,
                :cur_supply, :cur_return, :cur_delta, :cur_heat,
                :opt_total, :opt_host, :opt_tower, :opt_pump,
                :opt_supply, :opt_return, :opt_delta, :opt_heat,
                :diff_total, :diff_host, :diff_tower, :diff_pump,
                :diff_supply, :diff_return, :diff_delta, :diff_heat,
                :pct_total, :pct_host, :pct_tower, :pct_pump,
                :save_total, :save_pct,
                :ret_app, :diff_app, :fail_reasons, :remarks
            )
            """
            params = {
                'r_low': float(cfg.get('return_temp_lower_limit', 0)),
                'r_up': float(cfg.get('return_temp_upper_limit', 0)),
                's_low': float(cfg.get('supply_temp_lower_limit', 0)),
                's_up': float(cfg.get('supply_temp_upper_limit', 0)),
                'd_low': float(cfg.get('temp_diff_lower_limit', 0)),
                'd_up': float(cfg.get('temp_diff_upper_limit', 0)),
                'h_low': float(cfg.get('heat_dissipation_lower_limit', 0)),
                'h_up': float(cfg.get('heat_dissipation_upper_limit', 0)),
                'cur_total': float(cur['total_power']),
                'cur_host': float(cur['host_power']),
                'cur_tower': float(cur['cooling_tower_power']),
                'cur_pump': float(cur['cooling_pump_power']),
                'cur_supply': float(cur['cooling_inlet_temp']),
                'cur_return': float(cur['cooling_return_temp']),
                'cur_delta': float(cur['cooling_inlet_temp'] - cur['cooling_return_temp']),
                'cur_heat': 100.0,
                'opt_total': float(opt['total_power']),
                'opt_host': float(opt['host_power']),
                'opt_tower': float(opt['cooling_tower_power']),
                'opt_pump': float(opt['cooling_pump_power']),
                'opt_supply': float(opt['actual_inlet_temp']),
                'opt_return': float(opt['actual_return_temp']),
                'opt_delta': float(opt['delta_temp']),
                'opt_heat': float(opt.get('heat_dissipation_percent', 100.0)),
                'diff_total': float(diff_total), 'diff_host': float(diff_host),
                'diff_tower': float(diff_tower), 'diff_pump': float(diff_pump),
                'diff_supply': float(diff_supply), 'diff_return': float(diff_return),
                'diff_delta': float(diff_delta),
                'diff_heat': float(opt.get('heat_dissipation_percent', 100.0) - 100.0),
                'pct_total': float(pct_total), 'pct_host': float(pct_host),
                'pct_tower': float(pct_tower), 'pct_pump': float(pct_pump),
                'save_total': float(-diff_total), 'save_pct': float(pct_total),
                'ret_app': return_applied, 'diff_app': diff_applied,
                'fail_reasons': fail_str, 'remarks': remarks,
            }
            with self.postgres_engine.connect() as c:
                c.execute(text(query), params)
                c.commit()
            self.logger.info(f"结果已保存到 cooling_opt_parameters_total, 下发标记: 回水={return_applied}, 温差={diff_applied}")
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
            best = opt_result['optimal_result']
            desc = sorted(all_res, key=lambda x: x['total_power'], reverse=True)
            others = [r for r in desc if not (
                r['total_power'] == best['total_power'] and
                r['cooling_inlet_temp'] == best['cooling_inlet_temp'] and
                r['cooling_return_temp'] == best['cooling_return_temp']
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
                                  and c['cooling_inlet_temp']==r['cooling_inlet_temp']
                                  and c['cooling_return_temp']==r['cooling_return_temp']), idx+1)
                combos.append({
                    "index": orig_rank,
                    "cooling_inlet_temp": r['cooling_inlet_temp'],
                    "cooling_return_temp": r['cooling_return_temp'],
                    "actual_inlet_temp": r['actual_inlet_temp'],
                    "actual_return_temp": r['actual_return_temp'],
                    "delta_temp": r['delta_temp'],
                    "host_power": r['host_power'],
                    "cooling_pump_power": r['cooling_pump_power'],
                    "cooling_tower_power": r['cooling_tower_power'],
                    "total_power": r['total_power'],
                    "system_heat_dissipation": r.get('system_heat_dissipation', 0),
                    "heat_dissipation_percent": r.get('heat_dissipation_percent', 100.0),
                    "power_diff": r['power_diff'],
                    "power_diff_percent": r['power_diff_percent'],
                })
            cache = {"timestamp": datetime.now().isoformat(), "combinations": combos}
            key = self.opt_cfg["redis_key_pattern"].format(program_name=settings.PROGRAM_NAME)
            self.redis_client.setex(key, 300, json.dumps(cache, ensure_ascii=False))
            self.logger.info(f"Redis 缓存 {len(combos)} 个组合 -> {key}")
        except Exception as e:
            self.logger.error(f"Redis 缓存失败: {e}")


def main():
    scheduler = CoolingTempSchedulerTotal()
    scheduler.start_scheduler()


if __name__ == "__main__":
    main()
