//js/pages/config-api.js
const CONFIG_API_BASE = 'http://localhost:8000/api/v1/config';

const API = {
    // 数据源管理
    DATA_SOURCES: `${CONFIG_API_BASE}/data-sources`,
    DATA_SOURCE: (id) => `${CONFIG_API_BASE}/data-sources/${id}`,
    TEST_CONNECTION: `${CONFIG_API_BASE}/data-sources/test`,
    MAPPING_PROJECT: (data_source_id, database) => `${CONFIG_API_BASE}/mapping/project?data_source_id=${data_source_id}&database=${database}`,
    MAPPING_DEVICE: (project_id) => `${CONFIG_API_BASE}/mapping/device?project_id=${project_id}`,
    MAPPING_DEVICE_FEATURES: (device_id) => `${CONFIG_API_BASE}/mapping/device/${device_id}/features`,
    // MySQL特征表查询（新增）
    MYSQL_FEATURE_TABLES: (data_source_id, database) => `${CONFIG_API_BASE}/mapping/mysql_featuretables?data_source_id=${data_source_id}&database=${database}`,
     // 特征映射管理（新增）
    FEATURE_MAPPINGS: (device_id) => `${CONFIG_API_BASE}/feature-mappings/${device_id}`,
    FEATURE_MAPPINGS_SAVE: `${CONFIG_API_BASE}/feature-mappings`,
    FEATURE_MAPPINGS_BATCH_SAVE: `${CONFIG_API_BASE}/feature-mappings/batch`,
    FEATURE_MAPPINGS_DELETE: (mapping_id) => `${CONFIG_API_BASE}/feature-mappings/${mapping_id}`,
    FEATURE_MAPPINGS_TEST: (mapping_id) => `${CONFIG_API_BASE}/feature-mappings/${mapping_id}/test`,

    // 数据库和表管理
    DATABASES: (dataSourceId) => `${CONFIG_API_BASE}/data-sources/${dataSourceId}/databases`,
    TABLES: (dataSourceId, database) => `${CONFIG_API_BASE}/data-sources/${dataSourceId}/databases/${database}/tables`,
    CREATE_TABLE: (data_source_id, database) => `${CONFIG_API_BASE}/data-sources/${data_source_id}/databases/${database}/create-table`,
    // 特征映射
    MAPPING: `${CONFIG_API_BASE}/mappings`,
    MAPPING_BY_SOURCE: (dataSourceId, database) => `${CONFIG_API_BASE}/mappings/${dataSourceId}/${database}`,

};

// 将 API 对象添加到 window 全局对象
window.API = API;