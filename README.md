# Moonraker Reminder

一个用于监控 Moonraker 打印机状态的 Python 通知器，当打印机状态发生变化时会发送系统通知。

## 功能特性

- 🔄 每 10 秒自动查询打印机状态
- 📢 打印状态变化时发送系统通知
- 🛡️ 支持主机和备用主机双重保障
- 🔕 免打扰模式（DND）
- 🖥️ 系统托盘图标支持
- 📝 支持多台打印机同时监控
- ⚙️ YAML 配置文件，易于管理

## 安装步骤

### 1. 克隆或下载项目

```bash
cd moonraker-reminder
```

### 2. 安装 Python 依赖

使用 conda 环境（推荐）：
```bash
conda create -n moonraker-reminder python=3.10
conda activate moonraker-reminder
pip install -r requirements.txt
```

或使用 pip：
```bash
pip install -r requirements.txt
```

### 3. 配置打印机

编辑 `config.yaml` 文件，添加你的打印机配置：

```yaml
printers:
  - name: "我的打印机"
    host: "http://192.168.1.100"
    backup_host: "http://192.168.1.101"  # 可选
    api_key: "your_api_key_here"
  
  - name: "打印机2"
    host: "http://printer2.local"
    backup_host: ""
    api_key: "another_api_key"
```

**配置说明：**
- `name`: 打印机名称，用于通知显示
- `host`: 主要的 Moonraker API 地址
- `backup_host`: 备用地址（可选），主机超时时自动切换
- `api_key`: Moonraker API 密钥

## 使用方法

### 启动程序

```bash
python main.py
```

启动后，程序会在系统托盘显示一个图标。

### 系统托盘功能

右键点击托盘图标可以：
- ☑️ **免打扰模式**：开启后不会发送通知（但仍会监控状态）
- ❌ **退出**：停止监控并退出程序

## 工作原理

1. 程序每 10 秒向 Moonraker API 发送请求：
   ```
   GET {HOST}/printer/objects/query?print_stats=state&display_status=progress
   Headers: X-Api-Key: {APIKEY}
   ```

2. 解析返回的 JSON 数据，提取打印机状态

3. 比较当前状态与上次状态，如果发生变化则发送通知

4. 通知格式：`{打印机名称} 当前状态为 {状态}`

## 打印机状态说明

常见的打印机状态包括：
- `standby` - 待机
- `printing` - 打印中
- `paused` - 已暂停
- `complete` - 完成
- `error` - 错误

## 故障排除

### Windows 通知不显示

如果在 Windows 上通知不显示，请检查：
1. 系统设置 → 通知 → 确保通知已开启
2. 尝试手动测试通知功能

### 连接超时

- 程序默认超时时间为 30 秒
- 如果主机超时，会自动尝试 `backup_host`
- 确保防火墙允许访问 Moonraker API

### API 密钥获取

在 Moonraker 配置文件中查找或生成 API 密钥：
```ini
[authorization]
trusted_clients:
    192.168.1.0/24
```

## 依赖库

- `PyYAML` - YAML 配置文件解析
- `requests` - HTTP 请求
- `plyer` - 跨平台系统通知
- `pystray` - 系统托盘图标
- `Pillow` - 图标生成

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v1.0.0 (2026-02-28)
- 初始版本
- 支持多打印机监控
- 系统托盘集成
- 免打扰模式
- 备用主机支持
