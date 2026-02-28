# -*- coding: utf-8 -*-
"""
Moonraker Printer Status Reminder
监控 Moonraker 打印机状态并在状态变化时发送通知
"""

import time
import yaml
import requests
import threading
import webbrowser
from pathlib import Path
from plyer import notification
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PrinterMonitor:
    """打印机监控器"""
    
    def __init__(self, config_file='config.yaml'):
        self.config_file = config_file
        self.printers = []
        self.printer_states = {}  # 存储每个打印机的上一次状态
        self.running = False
        self.dnd_mode = False  # 免打扰模式
        self.icon = None
        self.load_config()
        
    def load_config(self):
        """加载配置文件"""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.error(f"配置文件不存在: {self.config_file}")
                raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.printers = config.get('printers', [])
                logger.info(f"成功加载 {len(self.printers)} 个打印机配置")
                
                # 初始化打印机状态
                for printer in self.printers:
                    printer_name = printer.get('name', 'Unknown')
                    self.printer_states[printer_name] = None
                    
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def query_printer(self, printer):
        """查询单个打印机状态"""
        name = printer.get('name', 'Unknown')
        host = printer.get('host')
        backup_host = printer.get('backup_host')
        api_key = printer.get('api_key')
        
        if not host or not api_key:
            logger.warning(f"打印机 {name} 配置不完整")
            return None
        
        url = f"{host}/printer/objects/query?print_stats=state&display_status=progress"
        headers = {'X-Api-Key': api_key}
        timeout = 5
        
        # 尝试主机
        try:
            logger.debug(f"正在查询 {name} ({host})")
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return self.parse_response(data)
        except requests.exceptions.Timeout:
            logger.warning(f"{name} 主机请求超时，尝试备用主机")
        except requests.exceptions.RequestException as e:
            logger.warning(f"{name} 主机请求失败: {e}")
        
        # 尝试备用主机
        if backup_host:
            try:
                url = f"{backup_host}/printer/objects/query?print_stats=state&display_status=progress"
                logger.debug(f"正在查询 {name} 备用主机 ({backup_host})")
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                return self.parse_response(data)
            except requests.exceptions.RequestException as e:
                logger.error(f"{name} 备用主机请求失败: {e}")
        
        # 发送错误通知
        if not self.dnd_mode:
            self.send_notification(
                f"{name} 错误",
                f"无法连接到打印机 {name}",
                timeout=5
            )
        return None
    
    def parse_response(self, data):
        """解析 API 响应"""
        try:
            status = data.get('result', {}).get('status', {})
            print_stats = status.get('print_stats', {})
            state = print_stats.get('state', 'unknown')
            
            display_status = status.get('display_status', {})
            progress = display_status.get('progress', 0.0)
            
            return {
                'state': state,
                'progress': progress
            }
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return None
    
    def send_notification(self, title, message, timeout=10):
        """发送系统通知"""
        try:
            notification.notify(
                title=title,
                message=message,
                app_name='Moonraker Reminder',
                timeout=timeout
            )
            logger.info(f"通知: {title} - {message}")
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
    
    def open_printer_url(self, url):
        """打开打印机网页"""
        if url:
            webbrowser.open(url)

    def create_callback(self, url):
        """创建回调函数以避免循环中的闭包问题"""
        return lambda icon, item: self.open_printer_url(url)

    def update_menu(self):
        """更新托盘菜单"""
        if self.icon:
            # 构建打印机状态菜单项
            printer_items = []
            for printer in self.printers:
                name = printer.get('name', 'Unknown')
                host = printer.get('host')
                
                status = self.printer_states.get(name)
                
                status_text = "未知"
                if status:
                    if isinstance(status, dict):
                        state = status.get('state', 'unknown')
                        progress = status.get('progress', 0)
                        status_text = f"{state}"
                        if state == "printing":
                            status_text += f" ({progress*100:.0f}%)"
                    else:
                        status_text = str(status)
                
                # 使用辅助方法创建回调，确保闭包变量正确且 lambda 参数数量符合 pystray 要求
                printer_items.append(MenuItem(
                    f"{name}: {status_text}", 
                    self.create_callback(host),
                    enabled=True
                ))
            
            # 添加分隔线
            if printer_items:
                printer_items.append(Menu.SEPARATOR)
                
            # 标准菜单项
            standard_items = [
                MenuItem(
                    "免打扰模式",
                    self.on_dnd_clicked,
                    checked=lambda item: self.dnd_mode
                ),
                MenuItem("退出", self.on_exit_clicked)
            ]
            
            self.icon.menu = Menu(*(printer_items + standard_items))

    def on_dnd_clicked(self, icon, item):
        """免打扰点击回调"""
        self.toggle_dnd()

    def on_exit_clicked(self, icon, item):
        """退出点击回调"""
        self.stop()
        icon.stop()

    def check_all_printers(self):
        """检查所有打印机状态"""
        for printer in self.printers:
            name = printer.get('name', 'Unknown')
            current_status = self.query_printer(printer)
            
            if current_status:
                current_state = current_status['state']
                # 获取旧状态
                previous_data = self.printer_states.get(name)
                previous_state = previous_data.get('state') if isinstance(previous_data, dict) else previous_data
                
                # 检查状态是否变化
                if previous_state and previous_state != current_state:
                    logger.info(f"{name} 状态变化: {previous_state} -> {current_state}")
                    
                    # 发送通知（除非在免打扰模式）
                    if not self.dnd_mode:
                        progress = current_status['progress']
                        message = f"当前状态: {current_state}"
                        if current_state == 'printing':
                            message += f"\n进度: {progress*100:.1f}%"
                        
                        self.send_notification(
                            f"{name}",
                            message,
                            timeout=10
                        )
                
                # 更新状态
                self.printer_states[name] = current_status
        
        # 检查完一轮后更新菜单
        self.update_menu()


    
    def monitor_loop(self):
        """监控循环"""
        logger.info("监控循环已启动")
        while self.running:
            try:
                self.check_all_printers()
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
            
            # 等待 60 秒
            time.sleep(10)
        
        logger.info("监控循环已停止")
    
    def start(self):
        """启动监控"""
        if self.running:
            logger.warning("监控已在运行中")
            return
        
        self.running = True
        
        # 在后台线程中运行监控循环
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        logger.info("正在停止监控...")
    
    def toggle_dnd(self):
        """切换免打扰模式"""
        self.dnd_mode = not self.dnd_mode
        status = "开启" if self.dnd_mode else "关闭"
        logger.info(f"免打扰模式已{status}")
        
        # 更新菜单状态
        self.update_menu()
        self.update_icon()
        
        # 可选：发送一个通知提示模式切换
        if not self.dnd_mode:
            self.send_notification(
                "免打扰模式",
                f"免打扰模式已{status}",
                timeout=3
            )
    
    def on_dnd_clicked(self, icon, item):
        """免打扰点击回调"""
        self.toggle_dnd()

    def on_exit_clicked(self, icon, item):
        """退出点击回调"""
        self.stop()
        icon.stop()
    
    def create_image(self):
        """创建托盘图标"""
        # 尝试加载本地的 icon.ico 文件
        icon_path = Path('icon.ico')
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.warning(f"加载 icon.ico 失败: {e}，使用默认图标")
        
        # 如果文件不存在或加载失败，创建一个简单的图标（64x64）
        width = 64
        height = 64
        color1 = (255, 255, 255)
        color2 = (100, 100, 100) if self.dnd_mode else (0, 120, 215)
        
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle(
            [(width // 4, height // 4), (width * 3 // 4, height * 3 // 4)],
            fill=color2
        )
        
        return image
    
    def update_icon(self):
        """更新托盘图标"""
        if self.icon:
            self.icon.icon = self.create_image()
    
    def setup_tray(self):
        """设置系统托盘"""
        # 创建图标对象
        self.icon = Icon(
            "Moonraker Reminder",
            self.create_image(),
            "Moonraker 打印机监控"
        )
        # 初始化菜单
        self.update_menu()

    
    def run(self):
        """运行程序"""
        self.setup_tray()
        self.start()
        
        # 运行托盘图标（这会阻塞主线程）
        self.icon.run()


def main():
    """主函数"""
    try:
        monitor = PrinterMonitor('config.yaml')
        logger.info("Moonraker Reminder 已启动")
        monitor.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    except Exception as e:
        logger.error(f"程序错误: {e}")
        raise
    finally:
        logger.info("程序已退出")


if __name__ == '__main__':
    main()
