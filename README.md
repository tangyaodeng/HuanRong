Pre-local/
     frontend/
        index.html             # 主页面
        pages/
            config.html
            device.html
            project.html
            features.html
            model-training.html
            monitoring.html
        css/
            style.css         # 主样式
            dashboard.css     # 仪表板样式
            project.css
            components.css
        js/
            pages/
                config.js
                device.js
                device-api.js
                project.js
                project-api.js
                features.js
                features-api.js
                model-training.js
                model-training-api.js
            main.js           # 主JS
            api.js            # API封装
            charts.js         # ECharts封装
            utils.js
            components/       # 组件
                navbar.js
        assets/               # 图片等资源
    backend/
        ml/
            __init__.py
            data/
                preprocessor.py
                loader.py
                __init__.py
            models/
                trainer.py
                __init__.py
                    models/
                        __init__.py
                        host.py
            utlis/
                __init__.py
        app/
            __init__.py
            main.py              # FastAPI应用入口
            config.py           # 配置管理
            database.py         # 数据库连接
            models.py           # SQLAlchemy模型
            schemas.py          # Pydantic模型
            api/
                __init__.py
                projects.py     # 项目API
                device.py   
                config.py 
                model_training.py
            crud/
                __init__.py
                projects.py    
                device.py
                config.py 
                model_training.py
            dependencies/
                __init__.py
                database.py
        tests/                  # 测试
            __init__.py
            pg-connect.py
            api.py
        requirements.txt
        .env
    scripts/                  # 部署脚本
    README.md
