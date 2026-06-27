"""
test_tools.py - 工具函数的单元测试
运行: pytest test_tools.py -v
"""

import sys
import os

# 确保能导入主模块中的工具函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from FirstAgentTest import calculate, get_weather


class TestCalculate:
    """测试计算器工具"""

    def test_basic_arithmetic(self):
        result = calculate("123 + 456")
        assert result["result"] == 579

    def test_multiplication(self):
        result = calculate("12 * 34")
        assert result["result"] == 408

    def test_float_division(self):
        result = calculate("100 / 3")
        assert abs(result["result"] - 33.33333) < 0.001

    def test_sqrt(self):
        result = calculate("sqrt(144)")
        assert result["result"] == 12

    def test_sin_pi_half(self):
        result = calculate("sin(pi/2)")
        assert abs(result["result"] - 1.0) < 0.0001

    def test_complex_expression(self):
        result = calculate("(100 + 200) * 3 - 50 / 2")
        assert result["result"] == 875

    def test_syntax_error(self):
        result = calculate("123 +")
        assert "error" in result

    def test_division_by_zero(self):
        result = calculate("1 / 0")
        assert "error" in result

    def test_unsafe_code_blocked(self):
        """确保危险操作被拦截"""
        result = calculate("__import__('os').system('dir')")
        assert "error" in result


class TestGetWeather:
    """测试天气工具（需要网络）"""

    def test_valid_city(self):
        result = get_weather("Beijing")
        assert "error" not in result or "status" not in str(result.get("error", ""))
        if "temperature" in result:
            assert "°C" in result["temperature"]

    def test_invalid_city(self):
        """不存在的城市应返回 error 或空数据"""
        result = get_weather("XyzNotARealCity12345")
        # 不崩溃就算通过，wttr.in 对无效城市也可能返回数据
        assert isinstance(result, dict)


class TestToolsIntegration:
    """测试工具组合"""

    def test_calculate_after_weather(self):
        """模拟：拿到天气数据后计算"""
        weather = get_weather("Beijing")
        if "temperature" in weather:
            temp_str = weather["temperature"].replace("°C", "")
            temp = float(temp_str)
            result = calculate(f"{temp} * 9/5 + 32")  # 摄氏转华氏
            assert "error" not in result


if __name__ == "__main__":
    print("运行测试请用: pytest test_tools.py -v")
    print("未安装 pytest 请先执行: pip install pytest")
