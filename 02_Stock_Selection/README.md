# 第二阶段：选股和通知系统

## 🎯 阶段目标
- 开发多因子选股策略
- 建立股票推荐系统
- 配置聚宽通知库
- 实现自动化选股流程

## 📁 核心文件
- `notification_lib.py` - 聚宽通知库（核心文件）
- `integrated_stock_selector.py` - 完整选股策略
- `ai_reference/` - AI参考策略
- `config/` - 配置文件

## 🚀 快速开始

### 步骤1：在聚宽研究根目录放置文件
```bash
# 将以下文件复制到聚宽研究根目录
notification_lib.py  # 通知库文件
```

### 步骤2：在策略中导入使用
```python
# 导入通知库
from notification_lib import *

def initialize(context):
    # 设置通知配置
    set_notification_config({
        'log_enabled': True,
        'email_enabled': True,
        'wechat_enabled': True
    })
    
    # 配置邮件通知
    set_email_config({
        'smtp_server': 'smtp.qq.com',
        'smtp_port': 587,
        'sender_email': 'your_email@qq.com',
        'sender_password': 'your_app_password',
        'recipients': ['recipient@example.com']
    })
    
    # 配置微信通知
    set_wechat_config({
        'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY',
        'secret': 'YOUR_SECRET'
    })
    
    # 设置选股频率
    run_monthly(fundamental_selection, monthday=1)
    run_weekly(technical_selection, weekday=1)

def fundamental_selection(context):
    # 执行选股逻辑
    selected_stocks = run_selection_logic()
    
    # 发送通知（邮件+微信+日志）
    send_stock_recommendation(selected_stocks, "基本面选股")
```

### 步骤3：查看选股结果
- 查看聚宽日志输出
- 检查邮件和微信通知
- 分析选股效果

## 📚 通知库功能

### 1. 股票推荐通知
```python
# 发送股票推荐通知
send_stock_recommendation(stocks_data, "基本面选股")

# stocks_data 格式：
stocks_data = [
    {
        'code': '000001.SZ',
        'name': '平安银行',
        'price': 12.50,
        'change_pct': 2.5,
        'reason': '基本面优秀'
    }
]
```

### 2. 每日报告通知
```python
# 发送每日报告
report_data = {
    'total_stocks': 25,
    'fundamental_stocks': 15,
    'technical_stocks': 8,
    'multi_factor_stocks': 12,
    'market_performance': '上涨2.5%',
    'hot_sectors': '科技、医药、新能源'
}
send_daily_report(report_data)
```

### 3. 预警通知
```python
# 发送预警通知
send_alert("选股预警", "选股数量不足", ["000001.SZ", "000002.SZ"])
```

### 4. 配置设置
```python
# 设置通知配置
set_notification_config({
    'log_enabled': True,      # 启用日志输出
    'email_enabled': True,    # 启用邮件通知
    'wechat_enabled': True    # 启用微信通知
})

# 配置邮件通知
set_email_config({
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 587,
    'sender_email': 'your_email@qq.com',
    'sender_password': 'your_app_password',
    'recipients': ['recipient@example.com']
})

# 配置微信通知
set_wechat_config({
    'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY',
    'secret': 'YOUR_SECRET'
})
```

## ⚙️ 通知配置说明

### 邮件通知配置
1. **获取邮箱授权码**：
   - QQ邮箱：设置 → 账户 → 开启SMTP服务 → 获取授权码
   - 163邮箱：设置 → POP3/SMTP/IMAP → 开启SMTP服务 → 获取授权码

2. **配置参数**：
   ```python
   set_email_config({
       'smtp_server': 'smtp.qq.com',        # QQ邮箱服务器
       'smtp_port': 587,                     # 端口号
       'sender_email': 'your_email@qq.com', # 发送邮箱
       'sender_password': 'your_app_password', # 授权码
       'recipients': ['recipient@example.com'] # 接收邮箱列表
   })
   ```

### 微信通知配置
1. **获取企业微信机器人**：
   - 企业微信 → 群聊 → 添加机器人 → 获取webhook地址

2. **配置参数**：
   ```python
   set_wechat_config({
       'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY',
       'secret': 'YOUR_SECRET'
   })
   ```

## 🔧 完整使用示例

### 基本面选股策略
```python
# -*- coding: utf-8 -*-
from notification_lib import *

def initialize(context):
    set_notification_config({'log_enabled': True})
    run_monthly(fundamental_selection, monthday=1)

def fundamental_selection(context):
    # 获取所有A股
    all_stocks = list(get_all_securities(['stock']).index)
    
    # 基本面筛选
    selected_stocks = []
    for stock in all_stocks[:100]:
        try:
            q = query(
                valuation.code,
                valuation.pe_ratio,
                indicator.roe
            ).filter(valuation.code == stock)
            
            df = get_fundamentals(q)
            if not df.empty:
                row = df.iloc[0]
                if row['roe'] > 15 and 0 < row['pe_ratio'] < 30:
                    selected_stocks.append(stock)
        except:
            continue
    
    # 获取股票详细信息
    stock_details = get_stock_details(selected_stocks[:20])
    
    # 发送通知
    send_stock_recommendation(stock_details, "基本面选股")
    
    return stock_details

def get_stock_details(stocks):
    stock_details = []
    for stock in stocks:
        try:
            stock_info = get_security_info(stock)
            hist = get_price(stock, count=2, frequency='daily', fields=['close'])
            
            if len(hist) >= 2:
                current_price = hist['close'][-1]
                prev_close = hist['close'][-2]
                change_pct = (current_price - prev_close) / prev_close * 100
                
                stock_details.append({
                    'code': stock,
                    'name': stock_info.display_name,
                    'price': current_price,
                    'change_pct': change_pct
                })
        except:
            continue
    
    return stock_details
```

## 📊 通知输出格式

### 股票推荐通知
```
=== 基本面选股 ===
推荐时间: 2024-01-15 09:30
推荐股票数量: 20只

1. 平安银行 (000001.SZ)
   价格: ¥12.50, 涨跌幅: 2.50%

2. 万科A (000002.SZ)
   价格: ¥18.30, 涨跌幅: -1.20%

⚠️ 投资有风险，入市需谨慎
```

### 每日报告通知
```
=== 每日选股报告 ===
报告日期: 2024-01-15

📊 选股统计:
- 总推荐股票: 25只
- 基本面选股: 15只
- 技术面选股: 8只
- 多因子选股: 12只

📋 市场概况:
- 市场表现: 上涨2.5%
- 热门板块: 科技、医药、新能源
```

## 🎯 使用建议

1. **文件放置**：将 `notification_lib.py` 放在聚宽研究根目录
2. **导入方式**：使用 `from notification_lib import *`
3. **配置设置**：在 `initialize` 函数中设置通知配置
4. **错误处理**：使用 try-except 处理通知发送错误

## 🔍 故障排除

- **导入错误**：确保 `notification_lib.py` 文件在聚宽研究根目录
- **函数调用错误**：确保正确导入了通知库
- **配置问题**：确保设置了 `log_enabled: True`

## 📊 选股策略说明

### 基本面选股
- ROE > 15%
- PE < 30
- 营收增长率 > 10%
- 负债率 < 60%

### 技术面选股
- 5日均线上穿20日均线
- MACD金叉
- RSI在30-70区间
- 成交量放大

### 多因子综合
- 基本面权重40%
- 技术面权重30%
- 市场情绪权重20%
- 估值水平权重10%

## 🔔 通知方式

### 邮件通知
- 每日股票推荐
- 重要市场变化
- 系统运行状态

### 微信通知
- 实时交易机会
- 风险提醒
- 简要市场概况

### 推荐报告
- 详细分析报告
- 图表可视化
- 历史表现追踪

## 📈 验收标准

完成第二阶段后，您应该能够：

1. **选股功能**
   - 每天自动筛选20-50只股票
   - 选股逻辑清晰可解释
   - 回测验证有效性

2. **通知功能**
   - 邮件通知正常发送
   - 微信通知及时到达
   - 通知内容格式美观

3. **推荐系统**
   - 每日定时推荐
   - 推荐报告完整
   - 系统运行稳定

---

**准备好开始选股和通知系统的开发了吗？**
