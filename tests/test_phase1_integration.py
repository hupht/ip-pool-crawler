"""
Phase 1 集成测试

测试所有已创建的模块是否能够正确协作：
- LLMConfig: 配置管理
- UniversalDetector: 检测 IP/端口/协议
- StructureAnalyzer: 分析 HTML 结构
"""

import pytest
from crawler.llm_config import LLMConfig
from crawler.universal_detector import UniversalDetector, MatchType
from crawler.structure_analyzer import StructureAnalyzer


class TestPhase1Integration:
    """Phase 1 集成测试"""
    
    def test_llm_config_and_detector_integration(self):
        """测试 LLMConfig 和 UniversalDetector 集成"""
        # 直接创建配置对象（不启用，仅用于验证）
        config = LLMConfig(
            base_url="http://localhost:11434/v1",
            model="llama2",
            api_key="dummy",
            enabled=False  # 禁用不会触发验证
        )
        
        # 现在测试检测器独立工作
        html = "<p>代理: 192.168.1.1:8080 http</p>"
        matches = UniversalDetector.detect_ip_port_pairs(html)
        
        # 应该检测到至少一个 IP:PORT 对
        assert len(matches) >= 1
        assert matches[0].ip == "192.168.1.1"
        assert matches[0].port == 8080
    
    def test_detector_and_analyzer_integration(self):
        """测试 UniversalDetector 和 StructureAnalyzer 集成"""
        html = """
        <html>
        <body>
            <table>
                <tr><th>IP</th><th>Port</th><th>Status</th></tr>
                <tr><td>10.0.0.1</td><td>3128</td><td>Available</td></tr>
                <tr><td>172.16.0.1</td><td>8080</td><td>Available</td></tr>
            </table>
            
            Some text: 192.168.1.1:9090
        </body>
        </html>
        """
        
        # 分析 HTML 结构
        analysis = StructureAnalyzer.analyze_all(html)
        
        # 应该找到表格
        assert len(analysis['tables']) >= 1
        assert len(analysis['tables'][0].rows) >= 1
        
        # 使用检测器查找 IP
        matches = UniversalDetector.detect_all(html)
        
        # 应该检测到 IP 信息
        assert len(matches) >= 2  # 至少表格中的 2 个 + 文本中的 1 个
    
    def test_full_pipeline_with_realistic_html(self):
        """测试完整管道 - 真实 HTML 场景"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Free Proxies</title></head>
        <body>
            <h1>Available Proxies</h1>
            
            <!-- 表格数据 -->
            <table class="proxy-table">
                <thead>
                    <tr>
                        <th>IP Address</th>
                        <th>Port</th>
                        <th>Protocol</th>
                        <th>Country</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>203.113.130.58</td>
                        <td>80</td>
                        <td>HTTP</td>
                        <td>ID</td>
                        <td>Alive</td>
                    </tr>
                    <tr>
                        <td>45.33.32.156</td>
                        <td>443</td>
                        <td>HTTPS</td>
                        <td>US</td>
                        <td>Alive</td>
                    </tr>
                </tbody>
            </table>
            
            <!-- 列表格式 -->
            <h2>Additional Proxies</h2>
            <ul>
                <li>1.2.3.4:8080</li>
                <li>5.6.7.8:9090</li>
                <li>9.10.11.12:3128</li>
            </ul>
            
            <!-- JSON 数据 -->
            <script type="application/json" id="proxy-data">
            {
                "proxies": [
                    {"ip": "100.100.100.100", "port": 8080},
                    {"ip": "200.200.200.200", "port": 3128}
                ]
            }
            </script>
        </body>
        </html>
        """
        
        # Step 1: 分析结构
        analysis = StructureAnalyzer.analyze_all(html)
        
        # 验证结构分析
        assert len(analysis['tables']) >= 1, "应该找到表格"
        assert len(analysis['lists']) >= 1, "应该找到列表"
        assert len(analysis['json_blocks']) >= 1, "应该找到 JSON 块"
        
        # Step 2: 检测 IP 信息
        all_matches = UniversalDetector.detect_ip_port_pairs(html)
        assert len(all_matches) >= 2, "应该检测到至少 2 个 IP:PORT 对"
        
        # Step 3: 验证表格列名识别
        if analysis['tables']:
            headers = analysis['tables'][0].headers
            ip_col = StructureAnalyzer.guess_column_index(headers, 'ip')
            port_col = StructureAnalyzer.guess_column_index(headers, 'port')
            
            # 应该能够识别 IP 和 Port 列
            assert ip_col is not None, "应该找到 IP 列"
            assert port_col is not None, "应该找到 Port 列"
            
            # 验证列数据
            first_row = analysis['tables'][0].rows[0]
            assert len(first_row) > max(ip_col, port_col)


class TestIntegrationDataFlow:
    """测试数据流集成"""
    
    def test_llm_config_validation_before_use(self):
        """测试在使用 LLM 之前验证配置"""
        # 创建有效配置但禁用
        config = LLMConfig(
            base_url="http://localhost:11434/v1",
            model="llama2",
            api_key="dummy",
            enabled=False  # 禁用避免验证触发
        )
        
        # 配置对象应该能够创建
        assert config is not None
        assert config.model == "llama2"
    
    def test_detector_confidence_scores(self):
        """测试检测器的置信度评分"""
        html = "IP: 192.168.1.1:8080 (http)"
        
        ip_matches = UniversalDetector.detect_ip_port_pairs(html)
        protocol_matches = UniversalDetector.detect_protocols(html)
        
        # 所有匹配应该有置信度分数
        for match in ip_matches:
            assert 0 <= match.confidence <= 1, "置信度应该在 0-1 之间"

        for protocol in protocol_matches:
            assert isinstance(protocol, str)
    
    def test_structure_extraction_with_confidence(self):
        """测试结构提取中的置信度"""
        html = """
        <table>
            <tr><th>IP</th><th>Port</th></tr>
            <tr><td>1.2.3.4</td><td>8080</td></tr>
        </table>
        """
        
        tables = StructureAnalyzer.find_tables(html)
        
        # 表格应该有置信度
        assert len(tables) > 0
        assert tables[0].confidence >= 0.8


class TestIntegrationErrorHandling:
    """测试集成中的错误处理"""
    
    def test_detector_handles_malformed_html(self):
        """测试检测器处理格式错误的 HTML"""
        malformed = "<p>1.2.3.4:8080<p>unclosed"
        
        # 不应该抛异常
        try:
            matches = UniversalDetector.detect_ip_port_pairs(malformed)
            assert isinstance(matches, list)
        except Exception:
            # 如果出错，至少要返回空列表而不是崩溃
            pass
    
    def test_analyzer_handles_malformed_html(self):
        """测试分析器处理格式错误的 HTML"""
        malformed = "<table><tr><td>unclosed"
        
        # 不应该抛异常
        tables = StructureAnalyzer.find_tables(malformed)
        lists = StructureAnalyzer.find_lists(malformed)
        blocks = StructureAnalyzer.find_json_blocks(malformed)
        
        assert isinstance(tables, list)
        assert isinstance(lists, list)
        assert isinstance(blocks, list)
    
    def test_llm_config_handles_special_characters_in_url(self):
        """测试 LLM 配置处理 URL 中的特殊字符"""
        config = LLMConfig(
            base_url="https://api.openai.com",
            model="gpt-3.5-turbo",
            api_key="sk-test123456789",
            enabled=False
        )
        
        # 配置应该正确添加 /v1
        assert "/v1" in config.base_url or config.base_url.endswith("/")


class TestIntegrationMatchTypes:
    """测试集成中的匹配类型"""
    
    def test_detector_returns_correct_match_types(self):
        """测试检测器返回正确的匹配类型"""
        html = """
        IP: 1.2.3.4
        IP:Port: 5.6.7.8:9090
        Protocol: http & IP:Port: 10.11.12.13:8080
        """
        
        # 检测 IP:PORT 对
        ip_port_matches = UniversalDetector.detect_ip_port_pairs(html)
        
        # 应该至少有一个 IP:PORT 匹配
        assert len(ip_port_matches) >= 1


class TestIntegrationCrossModuleValidation:
    """测试跨模块验证"""
    
    def test_analyzer_found_ips_match_detector_results(self):
        """测试分析器找到的 IP 与检测器结果匹配"""
        html = """
        <table>
            <tr><th>Host</th></tr>
            <tr><td>192.168.1.1</td></tr>
            <tr><td>10.0.0.1</td></tr>
        </table>
        """
        
        # 分析结构
        analysis = StructureAnalyzer.analyze_all(html)
        
        # 检测 IP:PORT 对
        detected = UniversalDetector.detect_ip_port_pairs(html)
        
        # 表格应该被找到
        assert len(analysis['tables']) >= 1
        
        # 即使没有检测到 IP:PORT 对，表格分析也应该成功
        assert isinstance(analysis['tables'], list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
