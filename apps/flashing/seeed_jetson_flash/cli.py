#!/usr/bin/env python3
"""
命令行接口模块
"""
import click
import json
import os
from pathlib import Path
from .flash import JetsonFlasher
from .recovery import RecoveryGuide


@click.group()
@click.version_option()
def cli():
    """Seeed Jetson Flash - 为 Jetson 设备刷机的工具"""
    pass


@cli.command()
@click.option('--product', '-p', required=True, help='产品型号 (例如: j4012mini)')
@click.option('--l4t', '-l', required=True, help='L4T 版本 (例如: 36.3.0)')
@click.option('--download-only', is_flag=True, help='仅下载固件，不刷写')
@click.option('--skip-verify', is_flag=True, help='跳过 SHA256 校验')
def flash(product, l4t, download_only, skip_verify):
    """刷写 Jetson 设备"""
    flasher = JetsonFlasher(product, l4t)
    
    click.echo(f"正在为 {product} 准备 L4T {l4t} 固件...")
    
    # 下载固件
    if not flasher.download_firmware():
        click.echo("固件下载失败", err=True)
        return
    
    # 校验固件
    if not skip_verify:
        if not flasher.verify_firmware():
            click.echo("固件校验失败", err=True)
            return
    
    if download_only:
        click.echo("固件下载完成")
        return
    
    # 解压固件
    if not flasher.extract_firmware():
        click.echo("固件解压失败", err=True)
        return
    
    # 刷写固件
    if not flasher.flash_firmware():
        click.echo("固件刷写失败", err=True)
        return
    
    click.echo("刷写完成！")


@cli.command()
@click.option('--product', '-p', required=True, help='产品型号')
def recovery(product):
    """显示进入 Recovery 模式的教程"""
    guide = RecoveryGuide(product)
    guide.show_guide()


@cli.command()
def list_products():
    """列出所有支持的产品"""
    data_path = Path(__file__).parent / "data" / "l4t_data.json"
    with open(data_path, 'r') as f:
        data = json.load(f)
    
    products = {}
    for item in data:
        product = item['product']
        if product not in products:
            products[product] = []
        products[product].append(item['l4t'])
    
    click.echo("支持的产品列表：\n")
    for product, l4t_versions in sorted(products.items()):
        click.echo(f"  {product}")
        click.echo(f"    L4T 版本: {', '.join(l4t_versions)}")
        click.echo()


@cli.command()
def gui():
    """启动图形界面"""
    try:
        # 直接导入 main 函数，避免通过 __init__.py
        import sys
        from pathlib import Path
        
        # 确保可以找到模块
        module_path = Path(__file__).parent
        if str(module_path) not in sys.path:
            sys.path.insert(0, str(module_path))
        
        from seeed_jetson_flash.gui.main_window import main as gui_main
        gui_main()
    except ImportError as e:
        click.echo(f"错误: 无法启动 GUI，请安装 PyQt5: pip install PyQt5", err=True)
        click.echo(f"详细错误: {e}", err=True)


def main():
    cli()


if __name__ == '__main__':
    main()
