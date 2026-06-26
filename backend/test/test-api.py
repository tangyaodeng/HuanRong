# backend/tests/api_test.py (或保持 api.py)
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"


def test_api():
    """测试所有项目管理API"""

    print("=== 项目管理API测试 ===\n")

    # 1. 测试获取项目列表
    print("1. 测试获取项目列表...")
    try:
        response = requests.get(f"{BASE_URL}/projects?page=1&page_size=5")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   项目数量: {len(data.get('projects', []))}")
            print(f"   总数: {data.get('total', 0)}")
        else:
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"   请求失败: {e}")
    print()

    # 2. 测试获取统计信息
    print("2. 测试获取统计信息...")
    try:
        response = requests.get(f"{BASE_URL}/projects/stats")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   统计信息: {data}")
        else:
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"   请求失败: {e}")
    print()

    # 3. 测试创建新项目
    print("3. 测试创建新项目...")
    new_project = {
        "name": "测试API项目",
        "code": "API_TEST_001",
        "description": "通过API创建的测试项目",
        "status": "active",
        "tags": ["测试", "API", "自动化"]
    }

    try:
        response = requests.post(f"{BASE_URL}/projects", json=new_project)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            print(f"   创建成功，项目ID: {data.get('id')}")
            project_id = data.get('id')
        else:
            print(f"   错误: {response.text}")
            project_id = 1  # 使用现有ID继续测试
    except Exception as e:
        print(f"   请求失败: {e}")
        project_id = 1
    print()

    # 4. 测试获取单个项目
    print("4. 测试获取单个项目...")
    try:
        response = requests.get(f"{BASE_URL}/projects/{project_id}")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   项目名称: {data.get('name')}")
        else:
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"   请求失败: {e}")
    print()

    # 5. 测试更新项目
    print("5. 测试更新项目...")
    update_data = {
        "description": "更新后的项目描述",
        "tags": ["测试", "更新"]
    }
    try:
        response = requests.put(f"{BASE_URL}/projects/{project_id}", json=update_data)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   更新成功")
        else:
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"   请求失败: {e}")
    print()

    # 6. 测试获取设备列表
    print("6. 测试获取项目设备列表...")
    try:
        response = requests.get(f"{BASE_URL}/projects/{project_id}/devices")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   设备数量: {len(data.get('devices', []))}")
        else:
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"   请求失败: {e}")
    print()

    # 7. 测试获取项目概览
    print("7. 测试获取项目概览...")
    try:
        response = requests.get(f"{BASE_URL}/projects/{project_id}/overview")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   概览信息获取成功")
        else:
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"   请求失败: {e}")
    print()

    print("=== API测试完成 ===")


if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        print("请确保后端服务正在运行: uvicorn app.main:app --reload")