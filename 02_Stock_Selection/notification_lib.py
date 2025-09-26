# -*- coding: utf-8 -*-
"""
聚宽通知库 - 重新设计版本
分离式通知功能，适用于聚宽平台

功能模块：
1. 普通通知 - 仅支持字符串发送
   - send_email(message)  # 发送邮件
   - send_wechat(message)  # 发送微信

2. HTML通知 - 支持数据渲染
   - send_html_email(subject, html_content)  # 发送HTML邮件

使用说明：
1. 将本文件放在聚宽研究根目录
2. 在策略中导入：from notification_lib import *
3. 配置通知参数并调用通知函数

配置示例：
# 邮件配置
set_email_config({
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 587,
    'sender_email': 'your_email@qq.com',
    'sender_password': 'your_app_password',
    'recipients': ['recipient@example.com']
})

# 微信配置
set_wechat_config({
    'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY'
})
"""

# 聚宽API导入
try:
    from kuanke.user_space_api import *
except:
    pass

import json
import smtplib
import ssl
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText as HTMLMIMEText
from datetime import datetime

class NotificationLib:
    """
    聚宽通知库类 - 重新设计版本
    """
    
    def __init__(self):
        """
        初始化通知库
        """
        # 邮件配置
        self.email_config = {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'recipients': []
        }
        
        # 微信配置
        self.wechat_config = {
            'webhook_url': ''
        }
    
    def detect_environment(self, context=None):
        """
        检测当前运行环境
        通过比较策略时间和实际时间来判断环境类型
        
        Returns:
            str: 环境标识 ('回测环境', '实盘环境', '未知环境')
        """
        try:
            if not context or not hasattr(context, 'current_dt'):
                return '未知环境'
            
            # 获取策略时间
            strategy_time = context.current_dt
            current_time = datetime.now()
            
            # 计算时间差（以天为单位）
            time_diff = abs((strategy_time - current_time).total_seconds() / 86400)
            
            # 如果时间差超过1天，认为是回测环境
            if time_diff > 1:
                return '回测环境'
            else:
                return '实盘环境'
                
        except Exception as e:
            log.warning(f"环境检测失败: {e}")
            return '未知环境'
    
    def markdown_to_html(self, markdown_content: str, title: str = "文档") -> str:
        """
        将Markdown内容转换为带样式的HTML
        
        Args:
            markdown_content: Markdown内容
            title: HTML页面标题
            
        Returns:
            完整的HTML内容
        """
        try:
            import markdown
            from datetime import datetime
            
            # HTML模板
            html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ 
            font-family: 'Microsoft YaHei', Arial, sans-serif; 
            line-height: 1.6; 
            margin: 40px; 
            background-color: #f5f5f5; 
            color: #333;
        }}
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }}
        h1 {{ 
            color: #2c3e50; 
            border-bottom: 3px solid #3498db; 
            padding-bottom: 10px; 
            margin-top: 0;
        }}
        h2 {{ 
            color: #34495e; 
            border-left: 4px solid #3498db; 
            padding-left: 15px; 
            margin-top: 30px; 
        }}
        h3 {{ 
            color: #7f8c8d; 
            margin-top: 25px;
        }}
        pre {{ 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 5px; 
            overflow-x: auto; 
            border-left: 4px solid #17a2b8;
            margin: 15px 0;
        }}
        code {{ 
            background: #f1f3f4; 
            padding: 2px 6px; 
            border-radius: 3px; 
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            margin: 20px 0;
            border: 1px solid #ddd;
        }}
        th, td {{ 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
        }}
        th {{ 
            background-color: #f2f2f2; 
            font-weight: bold; 
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            margin: 15px 0;
            padding: 10px 20px;
            background-color: #f9f9f9;
        }}
        .footer {{ 
            margin-top: 40px; 
            text-align: center; 
            color: #7f8c8d; 
            font-size: 0.9em;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        ul, ol {{
            margin: 15px 0;
            padding-left: 30px;
        }}
        li {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
        <div class="footer">
            <p>生成时间: {timestamp}</p>
        </div>
    </div>
</body>
</html>"""
            
            # 转换markdown为HTML
            html_content_body = markdown.markdown(
                markdown_content, 
                extensions=['tables', 'fenced_code', 'toc', 'codehilite']
            )
            
            # 生成完整HTML
            html_content = html_template.format(
                title=title,
                content=html_content_body,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            
            log.info(f"Markdown转换为HTML完成，内容长度: {len(html_content)}")
            return html_content
            
        except Exception as e:
            log.error(f"Markdown转换为HTML失败: {str(e)}")
            # 返回基础HTML
            return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title></head>
<body><pre>{markdown_content}</pre></body></html>"""
    
    # ==================== 普通通知功能 ====================
    
    def send_email(self, message, context=None):
        """
        发送普通邮件通知 - 仅支持字符串
        """
        try:
            if not self.email_config['sender_email'] or not self.email_config['recipients']:
                log.warning("邮件配置不完整，跳过邮件发送")
                return False
            
            # 检测环境并生成标题
            environment = self.detect_environment(context)
            subject = f"聚宽 [{environment}]"
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = ', '.join(self.email_config['recipients'])
            msg['Subject'] = subject
            
            # 添加邮件内容
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            # 发送邮件
            context = ssl.create_default_context()
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls(context=context)
                server.login(self.email_config['sender_email'], self.email_config['sender_password'])
                server.send_message(msg)
            
            log.info("邮件发送成功")
            return True
            
        except Exception as e:
            log.error(f"发送邮件失败: {e}")
            return False
    
    def send_wechat(self, message):
        """
        发送普通微信通知 - 仅支持字符串
        """
        try:
            if not self.wechat_config['webhook_url']:
                log.warning("微信配置不完整，跳过微信发送")
                return False
            
            # 构建消息
            wechat_message = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }
            
            # 发送请求
            response = requests.post(self.wechat_config['webhook_url'], json=wechat_message, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    log.info("微信消息发送成功")
                    return True
                else:
                    log.error(f"微信消息发送失败: {result.get('errmsg')}")
                    return False
            else:
                log.error(f"微信消息发送失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            log.error(f"发送微信消息失败: {e}")
            return False
    
    
    # ==================== HTML通知功能 ====================
    
    def send_html_email(self, strategy_name, context=None, selected_stocks=None, buy_signals=None, sell_signals=None, positions=None, total_return=None):
        """
        发送HTML邮件通知 - 智能渲染函数
        根据传入的数据自动判断要渲染哪些部分
        
        Args:
            strategy_name: 策略名称（必填）
            context: 聚宽上下文对象，用于获取策略时间
            selected_stocks: 选股列表，每个元素包含 {name, code, price, change_pct, reason}
            buy_signals: 开仓信号列表，每个元素包含 {stock, action, reason}
            sell_signals: 平仓信号列表，每个元素包含 {stock, action, reason}
            positions: 持仓列表，每个元素包含 {name, code, quantity, price, pnl}
            total_return: 总收益率（数字）
        """
        try:
            if not self.email_config['sender_email'] or not self.email_config['recipients']:
                log.warning("邮件配置不完整，跳过HTML邮件发送")
                return False
            
            # 生成HTML内容
            html_content = self.generate_smart_html(strategy_name, context, selected_stocks, buy_signals, sell_signals, positions, total_return)
            
            # 检测环境并生成邮件主题
            environment = self.detect_environment(context)
            subject_parts = [f"聚宽 - {strategy_name} [{environment}]"]
            if selected_stocks:
                subject_parts.append("选股结果")
            if buy_signals or sell_signals:
                subject_parts.append("交易信号")
            if positions is not None or total_return is not None:
                subject_parts.append("报告")
            
            subject = " - ".join(subject_parts)
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = ', '.join(self.email_config['recipients'])
            msg['Subject'] = subject
            
            # 添加HTML邮件内容
            msg.attach(HTMLMIMEText(html_content, 'html', 'utf-8'))
            
            # 发送邮件
            context = ssl.create_default_context()
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls(context=context)
                server.login(self.email_config['sender_email'], self.email_config['sender_password'])
                server.send_message(msg)
            
            log.info("HTML邮件发送成功")
            return True
            
        except Exception as e:
            log.error(f"发送HTML邮件失败: {e}")
            return False
    
    def send_html_email_raw(self, subject: str, html_content: str, context=None):
        """
        发送原始HTML邮件
        
        Args:
            subject: 邮件主题
            html_content: HTML内容
            context: 聚宽上下文对象
        """
        try:
            # 检查邮件配置
            if not self.email_config['sender_email'] or not self.email_config['sender_password']:
                log.warning("邮件配置不完整，跳过邮件发送")
                return False
            
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_config['sender_email']
            msg['To'] = ', '.join(self.email_config['recipients'])
            
            # 添加HTML内容
            html_part = HTMLMIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['sender_email'], self.email_config['sender_password'])
            
            text = msg.as_string()
            server.sendmail(self.email_config['sender_email'], self.email_config['recipients'], text)
            server.quit()
            
            log.info(f"HTML邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            log.error(f"发送HTML邮件失败: {e}")
            return False
    
    def generate_smart_html(self, strategy_name, context=None, selected_stocks=None, buy_signals=None, sell_signals=None, positions=None, total_return=None):
        """
        智能生成HTML内容 - 根据数据自动渲染相应部分
        """
        # 获取策略时间（回测虚拟时间）
        strategy_time = None
        if context and hasattr(context, 'current_dt'):
            strategy_time = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取当前系统时间
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # HTML头部
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{strategy_name} - 策略通知</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .section {{ margin: 20px 0; }}
                .section-title {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px; }}
                
                /* 选股样式 */
                .stock-item {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; }}
                .stock-code {{ font-weight: bold; color: #0066cc; font-size: 1.1em; }}
                .stock-price {{ color: #ff6600; }}
                .positive {{ color: #00aa00; font-weight: bold; }}
                .negative {{ color: #ff0000; font-weight: bold; }}
                
                /* 交易信号样式 */
                .signal-item {{ margin: 8px 0; padding: 8px; border-radius: 5px; }}
                .buy-signal {{ background-color: #d4edda; border-left: 4px solid #28a745; }}
                .sell-signal {{ background-color: #f8d7da; border-left: 4px solid #dc3545; }}
                
                /* 持仓样式 */
                .position-item {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background-color: #f8f9fa; }}
                .position-name {{ font-weight: bold; color: #333; }}
                
                /* 报告样式 */
                .summary {{ background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #007bff; }}
                .metric {{ font-size: 1.2em; margin: 5px 0; }}
                
                .warning {{ margin-top: 20px; padding: 10px; background-color: #fff3cd; border-radius: 5px; text-align: center; color: #856404; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📊 {strategy_name} - 策略通知</h2>
                <p>策略时间: {strategy_time if strategy_time else '未获取到'}</p>
                <p>通知时间: {current_time}</p>
            </div>
        """
        
        # 选股部分
        if selected_stocks:
            html += f"""
            <div class="section">
                <h3 class="section-title">📈 选股结果</h3>
                <p>推荐股票数量: <strong>{len(selected_stocks)}只</strong></p>
            """
            for i, stock in enumerate(selected_stocks, 1):
                change_pct = stock.get('change_pct', 0)
                change_class = 'positive' if change_pct >= 0 else 'negative'
                html += f"""
                <div class="stock-item">
                    <div class="stock-code">{i}. {stock.get('name', '')} ({stock.get('code', '')})</div>
                    <div class="stock-price">价格: ¥{stock.get('price', 0):.2f}</div>
                    <div class="{change_class}">涨跌幅: {change_pct:+.2f}%</div>
                    {f'<div style="margin-top: 5px; color: #666;">推荐理由: {stock.get("reason", "")}</div>' if stock.get('reason') else ''}
                </div>
                """
            html += "</div>"
        
        # 交易信号部分
        if buy_signals or sell_signals:
            html += '<div class="section"><h3 class="section-title">🔄 交易信号</h3>'
            
            if buy_signals:
                html += '<h4>🟢 开仓信号</h4>'
                for signal in buy_signals:
                    html += f"""
                    <div class="signal-item buy-signal">
                        <strong>{signal.get('stock', '')} - {signal.get('action', '买入')}</strong>
                        {f'<br><span style="color: #666;">理由: {signal.get("reason", "")}</span>' if signal.get('reason') else ''}
                    </div>
                    """
            
            if sell_signals:
                html += '<h4>🔴 平仓信号</h4>'
                for signal in sell_signals:
                    html += f"""
                    <div class="signal-item sell-signal">
                        <strong>{signal.get('stock', '')} - {signal.get('action', '卖出')}</strong>
                        {f'<br><span style="color: #666;">理由: {signal.get("reason", "")}</span>' if signal.get('reason') else ''}
                    </div>
                    """
            html += "</div>"
        
        # 持仓和收益报告部分
        if total_return is not None or positions:
            html += '<div class="section"><h3 class="section-title">📋 策略报告</h3>'
            
            if total_return is not None:
                return_class = 'positive' if total_return >= 0 else 'negative'
                html += f"""
                <div class="summary">
                    <h4>📈 策略表现</h4>
                    <div class="metric">总收益率: <span class="{return_class}">{total_return:+.2f}%</span></div>
                    {f'<div class="metric">持仓数量: {len(positions)}只</div>' if positions else ''}
                </div>
                """
            
            if positions:
                html += '<h4>💼 持仓明细</h4>'
                for position in positions:
                    pnl = position.get('pnl', 0)
                    pnl_class = 'positive' if pnl >= 0 else 'negative'
                    html += f"""
                    <div class="position-item">
                        <div class="position-name">{position.get('name', '')} ({position.get('code', '')})</div>
                        <div>持仓数量: {position.get('quantity', 0)}</div>
                        <div>当前价格: ¥{position.get('price', 0):.2f}</div>
                        <div>盈亏: <span class="{pnl_class}">{pnl:+.2f}%</span></div>
                    </div>
                    """
            html += "</div>"
        
        # 结尾
        html += """
            <div class="warning">
                <strong>⚠️ 投资有风险，入市需谨慎</strong>
            </div>
        </body>
        </html>
        """
        
        return html
    
    
    
    # ==================== 配置方法 ====================
    
    def set_email_config(self, email_config):
        """
        设置邮件配置
        """
        self.email_config.update(email_config)
        log.info("邮件配置已更新")
    
    def set_wechat_config(self, wechat_config):
        """
        设置微信配置
        """
        self.wechat_config.update(wechat_config)
        log.info("微信配置已更新")
    

# 创建全局通知库实例
notification_lib = NotificationLib()

# ==================== 导出函数 ====================

def detect_environment(context=None):
    """检测当前运行环境"""
    return notification_lib.detect_environment(context)

# 普通通知函数
def send_email(message, context=None):
    """发送普通邮件通知 - 仅支持字符串"""
    return notification_lib.send_email(message, context)

def send_wechat(message):
    """发送普通微信通知 - 仅支持字符串"""
    return notification_lib.send_wechat(message)

# HTML通知函数
def send_html_email(strategy_name, context=None, selected_stocks=None, buy_signals=None, sell_signals=None, positions=None, total_return=None):
    """发送HTML邮件通知 - 智能渲染函数，根据传入的数据自动判断要渲染哪些部分"""
    return notification_lib.send_html_email(strategy_name, context, selected_stocks, buy_signals, sell_signals, positions, total_return)

# 配置函数
def set_email_config(email_config):
    """设置邮件配置"""
    return notification_lib.set_email_config(email_config)

def set_wechat_config(wechat_config):
    """设置微信配置"""
    return notification_lib.set_wechat_config(wechat_config)

# Markdown相关函数
def markdown_to_html(markdown_content: str, title: str = "文档") -> str:
    """将Markdown内容转换为带样式的HTML"""
    return notification_lib.markdown_to_html(markdown_content, title)

def send_html_email_by_md(markdown_content: str, subject: str = "策略通知", title: str = "文档", context=None):
    """发送Markdown格式的HTML邮件"""
    try:
        # 转换为HTML
        html_content = notification_lib.markdown_to_html(markdown_content, title)
        
        # 发送HTML邮件
        return notification_lib.send_html_email_raw(subject, html_content, context)
    except Exception as e:
        log.error(f"发送Markdown邮件失败: {e}")
        return False

def send_unified_notification(content: str, subject: str = "策略通知", title: str = "文档", 
                            format_type: str = "html", context=None):
    """
    统一通知函数 - 根据格式类型发送不同格式的通知
    
    Args:
        content: 通知内容
        subject: 邮件主题
        title: 页面标题
        format_type: 通知格式 ('html', 'markdown', 'text')
        context: 聚宽上下文对象
    """
    try:
        if format_type == "html":
            # 直接发送HTML内容
            return notification_lib.send_html_email_raw(subject, content, context)
        elif format_type == "markdown":
            # 将Markdown转换为HTML后发送
            html_content = notification_lib.markdown_to_html(content, title)
            return notification_lib.send_html_email_raw(subject, html_content, context)
        elif format_type == "text":
            # 发送纯文本邮件
            return notification_lib.send_email(content, context)
        else:
            log.error(f"不支持的通知格式: {format_type}")
            return False
    except Exception as e:
        log.error(f"发送统一通知失败: {e}")
        return False

