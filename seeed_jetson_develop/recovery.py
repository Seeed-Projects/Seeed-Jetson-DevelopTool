"""
Recovery 模式教程模块
"""
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown


class RecoveryGuide:
    def __init__(self, product):
        self.product = product
        self.data_path = Path(__file__).parent / "data" / "recovery_guides.json"
        self.console = Console()
        self.guide_data = self._load_guide()
    
    def _load_guide(self):
        """加载 Recovery 教程数据"""
        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 查找产品对应的系列
        for series_key, series_data in data.items():
            if self.product in series_data['products']:
                return series_data
        
        raise ValueError(f"未找到 {self.product} 的 Recovery 教程")
    
    def show_guide(self):
        """显示 Recovery 模式教程"""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold cyan]{self.guide_data['name']} - 进入 Recovery 模式教程[/bold cyan]",
            border_style="cyan"
        ))
        self.console.print()
        
        # 显示所需设备
        self.console.print("[bold yellow]📋 所需设备:[/bold yellow]")
        for req in self.guide_data['requirements']:
            self.console.print(f"  • {req}")
        self.console.print()
        
        # 显示操作步骤
        self.console.print("[bold green]🔧 操作步骤:[/bold green]")
        for step in self.guide_data['steps']:
            self.console.print(f"  [bold]{step['step']}.[/bold] {step['description']}")
        self.console.print()
        
        # 显示验证方法
        verification = self.guide_data['verification']
        self.console.print("[bold blue]✓ 验证设备是否进入 Recovery 模式:[/bold blue]")
        self.console.print(f"  在终端执行: [cyan]{verification['command']}[/cyan]")
        self.console.print()
        self.console.print("  如果输出包含以下任一 ID，表示设备已进入 Recovery 模式：")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("模块", style="cyan")
        table.add_column("USB ID", style="green")
        
        for module, usb_id in verification['ids'].items():
            table.add_row(module, usb_id)
        
        self.console.print(table)
        self.console.print()
        
        # 显示参考图片
        if 'images' in self.guide_data:
            self.console.print("[bold magenta]📷 参考图片:[/bold magenta]")
            for img in self.guide_data['images']:
                self.console.print(f"  • {img['description']}")
                self.console.print(f"    {img['url']}")
            self.console.print()
        
        # 显示视频教程（如果有）
        if 'video' in self.guide_data:
            self.console.print("[bold red]🎥 视频教程:[/bold red]")
            self.console.print(f"  {self.guide_data['video']}")
            self.console.print()
        
        # 故障排除
        self.console.print("[bold yellow]⚠️  故障排除:[/bold yellow]")
        self.console.print("  如果设备未被检测到，请尝试：")
        self.console.print("  • 重新插拔 USB 数据线")
        self.console.print("  • 更换 USB 接口（优先使用 USB 2.0 口）")
        self.console.print("  • 确认设备处于 Recovery 模式")
        self.console.print()
