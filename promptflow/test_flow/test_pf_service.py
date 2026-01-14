# test_pf_service.py
import requests

def test_promptflow():
    response = requests.post(
        "http://localhost:8081/score",
        json={"name": "AI Platform"},
        headers={"Content-Type": "application/json"}
    )
    print("状态码:", response.status_code)
    print("响应:", response.json())
    return response.status_code == 200

if __name__ == "__main__":
    success = test_promptflow()
    print("服务测试:", "成功" if success else "失败")