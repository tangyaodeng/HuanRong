-- 插入trainer数据
INSERT INTO trainer_configs (device_id, trainer_path, trainer_type, is_primary, description) VALUES
    -- Device 8 配置
    (9, 'ml.models.trainers.device9_xgboost_v1.XGBoostTrainer', 'xgboost', TRUE, '设备9的主训练器')
--     ml.models.trainers.device7_xgboost_v1.XGBoostMultiStepTrainer   XGBoostTrainer

