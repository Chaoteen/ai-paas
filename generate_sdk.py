#!/usr/bin/env python3
"""
AIOS SDK生成脚本 - 逐个文件处理版本
"""

import os
import subprocess
import sys
from pathlib import Path

class SDKGenerator:
    def __init__(self):
        # 精确配置路径
        self.proto_dir = Path("/mnt/d/RD/ai-os/proto")
        self.sdk_base_dir = Path("/mnt/d/RD/ai-os/aios_sdk")
        self.python_out_dir = self.sdk_base_dir / "generated"
        self.grpc_out_dir = self.sdk_base_dir / "generated" / "grpc"
        
        # Proto文件列表
        self.proto_files = [
            "envelope.proto",  # 基础依赖放前面
            "agent.proto",
            "inference.proto", 
            "langgraph.proto",
            "model.proto",
            "policy.proto",
            "prompt.proto",
            "vector.proto"
        ]
        
    def check_environment(self):
        """检查生成环境"""
        print("🔍 检查生成环境...")
        
        # 检查proto目录
        if not self.proto_dir.exists():
            raise FileNotFoundError(f"Proto目录不存在: {self.proto_dir}")
        
        # 检查所有proto文件
        missing_files = []
        for proto_file in self.proto_files:
            if not (self.proto_dir / proto_file).exists():
                missing_files.append(proto_file)
        
        if missing_files:
            raise FileNotFoundError(f"缺少proto文件: {missing_files}")
        
        # 检查protoc版本
        try:
            result = subprocess.run(["protoc", "--version"], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("protoc编译器未安装或不可用")
        
        # 检查Python grpc工具
        try:
            import grpc_tools
            print("✅ grpc_tools可用")
        except ImportError:
            raise RuntimeError("请安装grpc-tools: pip install grpc-tools")
            
    def clean_old_files(self):
        """清理旧生成文件"""
        print("🧹 清理旧生成文件...")
        
        if self.python_out_dir.exists():
            import shutil
            shutil.rmtree(self.python_out_dir)
        
        # 重新创建目录
        self.python_out_dir.mkdir(exist_ok=True)
        self.grpc_out_dir.mkdir(exist_ok=True)
        
    def validate_proto_files(self):
        """逐个验证proto文件语法"""
        print("🔍 验证proto文件语法...")
        
        for proto_file in self.proto_files:
            print(f"  验证 {proto_file}...")
            cmd = [
                "protoc",
                f"-I{self.proto_dir}",
                f"--python_out=/tmp/validate",
                str(self.proto_dir / proto_file)
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"  ✅ {proto_file} 语法正确")
            except subprocess.CalledProcessError as e:
                print(f"  ❌ {proto_file} 语法错误:")
                error_lines = e.stderr.decode().split('\n')
                for line in error_lines:
                    if line.strip():
                        print(f"    {line}")
                # 继续验证其他文件，但记录问题
                continue
    
    def generate_python_sdk(self):
        """逐个生成Python SDK文件"""
        print("🔨 生成Python SDK...")
        
        successful_files = []
        failed_files = []
        
        for proto_file in self.proto_files:
            print(f"  生成 {proto_file}...")
            cmd = [
                sys.executable, "-m", "grpc_tools.protoc",
                f"-I{self.proto_dir}",
                f"--python_out={self.python_out_dir}",
                f"--grpc_python_out={self.grpc_out_dir}",
                str(self.proto_dir / proto_file)
            ]
            
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"  ✅ {proto_file} 生成成功")
                successful_files.append(proto_file)
            except subprocess.CalledProcessError as e:
                print(f"  ❌ {proto_file} 生成失败:")
                error_lines = e.stderr.split('\n')
                for line in error_lines:
                    if line.strip():
                        print(f"    {line}")
                failed_files.append(proto_file)
        
        # 报告生成结果
        print(f"\n📊 生成结果:")
        print(f"  ✅ 成功: {len(successful_files)} 个文件")
        print(f"  ❌ 失败: {len(failed_files)} 个文件")
        
        if failed_files:
            print(f"  失败文件: {', '.join(failed_files)}")
            raise RuntimeError(f"{len(failed_files)} 个文件生成失败")
    
    def fix_imports(self):
        """修复Python导入路径"""
        print("🔧 修复Python导入路径...")
        
        # 修复普通pb2文件的导入
        for file_path in self.python_out_dir.glob("*.py"):
            self._fix_single_file_imports(file_path)
        
        # 修复grpc pb2文件的导入  
        for file_path in self.grpc_out_dir.glob("*.py"):
            self._fix_single_file_imports(file_path)
            
    def _fix_single_file_imports(self, file_path):
        """修复单个文件的导入路径"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 修复相对导入
            for proto_name in [pf.replace('.proto', '') for pf in self.proto_files]:
                old_import = f"import {proto_name}_pb2"
                new_import = f"from . import {proto_name}_pb2"
                content = content.replace(old_import, new_import)
                
                # 修复grpc导入
                old_grpc_import = f"import {proto_name}_pb2_grpc"
                new_grpc_import = f"from ..generated.grpc import {proto_name}_pb2_grpc"
                content = content.replace(old_grpc_import, new_grpc_import)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            print(f"⚠️ 修复文件 {file_path} 时出错: {e}")
    
    def create_init_files(self):
        """创建包初始化文件"""
        print("📄 创建包初始化文件...")
        
        # 主包init
        init_content = '''"""
AIOS SDK - 自动生成的gRPC客户端库
基于proto文件生成，版本: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "AIOS Development Team"

import sys
import os

# 添加当前路径到Python路径
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
'''
        
        with open(self.python_out_dir / "__init__.py", "w") as f:
            f.write(init_content)
        
        with open(self.grpc_out_dir / "__init__.py", "w") as f:
            f.write('''"""
gRPC生成的客户端和服务端代码
"""\n''')
    
    def run(self):
        """执行完整的生成流程"""
        print("🚀 开始生成AIOS SDK...")
        
        try:
            self.check_environment()
            self.clean_old_files()
            self.validate_proto_files()  # 新增验证步骤
            self.generate_python_sdk()
            self.fix_imports()
            self.create_init_files()
            
            print(f"✅ AIOS SDK生成完成!")
            print(f"📁 生成位置: {self.python_out_dir}")
            print(f"📁 gRPC代码: {self.grpc_out_dir}")
            
        except Exception as e:
            print(f"❌ SDK生成失败: {e}")
            sys.exit(1)

if __name__ == "__main__":
    generator = SDKGenerator()
    generator.run()