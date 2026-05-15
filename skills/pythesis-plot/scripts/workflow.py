#!/usr/bin/env python3
"""
PyThesisPlot 主工作流脚本
完整流程：数据接收 -> 分析 -> 建议 -> 确认 -> 生成
"""

import os
import sys
import shutil
import json
import argparse
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_SITE = SKILL_DIR / "vendor" / "site-packages"
if VENDOR_SITE.exists():
    sys.path.insert(0, str(VENDOR_SITE))

# 修复 Windows GBK 编码问题（确保 emoji 和中文正常输出）
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_analyzer import DataAnalyzer
from plot_generator import PlotGenerator


class WorkflowManager:
    """工作流管理器"""
    
    def __init__(self, output_base="output"):
        self.output_base = output_base
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.work_dir = None
        self.original_filename = None
        
    def setup_work_directory(self, input_file):
        """
        创建工作目录，保存上传的文件
        
        命名规范: output/YYYYMMDD-HHMMSS-原文件名/
        """
        self.original_filename = Path(input_file).stem
        dir_name = f"{self.timestamp}-{self.original_filename}"
        self.work_dir = os.path.join(self.output_base, dir_name)
        
        # 创建目录
        os.makedirs(self.work_dir, exist_ok=True)
        print(f"[DIR] Work directory: {self.work_dir}")
        
        # 复制并重命名文件
        ext = Path(input_file).suffix
        saved_name = f"{self.timestamp}-{self.original_filename}{ext}"
        saved_path = os.path.join(self.work_dir, saved_name)
        shutil.copy2(input_file, saved_path)
        print(f"[DATA] Saved file: {saved_name}")
        
        return saved_path
    
    def analyze_data(self, data_file):
        """执行数据分析"""
        print("\n[ANALYZE] Analyzing data...")
        analyzer = DataAnalyzer(data_file)
        report = analyzer.generate_report()
        
        # 保存分析报告
        report_path = os.path.join(self.work_dir, "analysis_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print("[REPORT] analysis_report.md")
        
        return report, analyzer.suggestions
    
    def generate_plots(self, config):
        """
        生成图表
        
        输出到工作目录，同时生成PDF和PNG
        """
        print("\n[PLOT] Generating charts...")
        generator = PlotGenerator(config, self.work_dir, self.timestamp)
        generated_files = generator.generate()
        
        print(f"[OK] Generated {len(generated_files)} charts")
        for f in generated_files:
            print(f"   {os.path.basename(f)}")
        
        return generated_files
    
    def save_plot_config(self, config):
        """保存图表配置"""
        config_path = os.path.join(self.work_dir, "plot_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("[CONFIG] plot_config.json")


def print_analysis_report(report, suggestions):
    """打印分析报告（用于展示给用户）"""
    print("\n" + "="*60)
    print(report)
    print("="*60)


def normalize_selection(value):
    """Normalize interactive or piped selection text from Windows consoles."""
    cleaned = value.strip().lstrip("\ufeff")
    if cleaned.lower().endswith("all") and len(cleaned) <= 8:
        return "all"
    if cleaned.startswith("锘") and cleaned.lower().endswith("ll"):
        return "all"
    return cleaned


def main():
    parser = argparse.ArgumentParser(
        description="PyThesisPlot 完整工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 完整工作流
  python workflow.py --input data.csv
  
  # 仅分析
  python workflow.py --input data.csv --analyze-only
  
  # 从配置生成
  python workflow.py --config plot_config.json
        """
    )
    parser.add_argument('--input', '-i', help='输入数据文件')
    parser.add_argument('--config', '-c', help='图表配置文件（跳过分析阶段）')
    parser.add_argument('--output-dir', '-o', default='output', 
                       help='输出目录基础路径 (默认: output)')
    parser.add_argument('--analyze-only', action='store_true',
                       help='仅执行数据分析')
    
    args = parser.parse_args()
    
    if not args.input and not args.config:
        parser.print_help()
        sys.exit(1)
    
    # 初始化工作流
    workflow = WorkflowManager(args.output_dir)
    
    if args.config:
        # 从配置直接生成
        print("[CONFIG] Generating charts from config...")
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        workflow.work_dir = os.path.dirname(args.config) or "."
        workflow.timestamp = config.get('timestamp', workflow.timestamp)
        workflow.generate_plots(config)
        
    elif args.input:
        # 完整工作流
        if not os.path.exists(args.input):
            print(f"[ERROR] File not found: {args.input}")
            sys.exit(1)
        
        # 阶段1: 设置工作目录
        print("="*60)
        print("阶段1: 数据接收")
        print("="*60)
        data_file = workflow.setup_work_directory(args.input)
        
        # 阶段2: 数据分析
        print("\n" + "="*60)
        print("阶段2: 数据分析")
        print("="*60)
        report, suggestions = workflow.analyze_data(data_file)
        
        # 展示分析报告
        print_analysis_report(report, suggestions)
        
        if args.analyze_only:
            print("\n[OK] Analysis complete; waiting for user confirmation before plotting")
            return
        
        # 阶段3: 用户确认（模拟交互）
        print("\n" + "="*60)
        print("阶段3: 用户确认")
        print("="*60)
        print("\n[HINT] In normal use, pause here and wait for user confirmation.")
        print("   用户可以说: '生成方案1和2' / '全部生成' / '修改...'")
        
        # 模拟用户选择（实际使用时需要交互）
        selected = normalize_selection(input("\n请输入要生成的方案编号（如: 1,2 或 all）: "))
        
        # 阶段4: 生成
        print("\n" + "="*60)
        print("阶段4: 生成图表")
        print("="*60)
        
        # 根据选择生成配置
        if selected.lower() == 'all':
            selected_indices = list(range(len(suggestions)))
        else:
            selected_indices = [int(x.strip()) - 1 for x in selected.split(',')]
        
        config = {
            'timestamp': workflow.timestamp,
            'data_file': data_file,
            'original_file': args.input,
            'plots': [suggestions[i] for i in selected_indices if 0 <= i < len(suggestions)]
        }
        
        # 保存配置
        workflow.save_plot_config(config)
        
        # 生成图表
        workflow.generate_plots(config)
        
        print("\n" + "="*60)
        print("[OK] Complete")
        print(f"[DIR] All files saved to: {workflow.work_dir}")
        print("="*60)


if __name__ == '__main__':
    main()
