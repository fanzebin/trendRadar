#!/usr/bin/env python3
"""
LiveATC 实时音频转存脚本

由于 LiveATC.net 使用 Cloudflare 保护，无法直接通过简单请求获取音频流。
本脚本提供几种方法来转存实时音频：

方法 1: 如果您已知直接的音频流 URL (Icecast/Shoutcast 流)
方法 2: 使用 selenium/playwright 通过浏览器获取真实流 URL
方法 3: 手动从浏览器开发者工具中获取流 URL

使用方法:
    python liveatc_recorder.py --url <STREAM_URL> --output <OUTPUT_FILE>
    
示例:
    python liveatc_recorder.py --url "http://example.com:8000/stream.mp3" --output rpll_audio.mp3

注意:
    LiveATC 的真实流 URL 通常格式为:
    http://a[1-9].liveatc.net/[icao_code]
    例如：http://a1.liveatc.net/rpll
    
    但由于 DNS 解析问题，建议先从浏览器中获取实际可用的流 URL
"""

import argparse
import sys
import signal
import threading
from pathlib import Path
from datetime import datetime


def signal_handler(signum, frame):
    """处理中断信号"""
    print("\n收到中断信号，正在停止录制...")
    sys.exit(0)


class AudioRecorder:
    """音频录制器类"""
    
    def __init__(self, stream_url: str, output_file: str, chunk_size: int = 8192):
        """
        初始化录制器
        
        Args:
            stream_url: 音频流 URL (Icecast/Shoutcast 流)
            output_file: 输出文件路径
            chunk_size: 每次读取的字节数
        """
        self.stream_url = stream_url
        self.output_file = output_file
        self.chunk_size = chunk_size
        self.is_recording = False
        self.total_bytes = 0
        self.start_time = None
    
    def record_with_requests(self, duration: int = None):
        """
        使用 requests 库录制音频流
        
        Args:
            duration: 录制时长（秒），None 表示无限录制
        """
        try:
            import requests
        except ImportError:
            print("错误：需要安装 requests 库")
            print("运行：pip install requests")
            return False
        
        print(f"开始连接到音频流：{self.stream_url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(self.stream_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            print(f"连接成功！状态码：{response.status_code}")
            print(f"内容类型：{response.headers.get('content-type', 'unknown')}")
            print(f"开始录制到：{self.output_file}")
            
            self.is_recording = True
            self.start_time = datetime.now()
            self.total_bytes = 0
            
            with open(self.output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if not self.is_recording:
                        break
                    
                    if chunk:
                        f.write(chunk)
                        self.total_bytes += len(chunk)
                        
                        # 每 10MB 显示一次进度
                        if self.total_bytes % (10 * 1024 * 1024) < self.chunk_size:
                            elapsed = (datetime.now() - self.start_time).total_seconds()
                            rate = self.total_bytes / elapsed if elapsed > 0 else 0
                            print(f"已录制：{self.total_bytes / 1024 / 1024:.2f} MB, "
                                  f"时长：{elapsed:.1f}s, 速率：{rate/1024:.1f} KB/s")
                    
                    # 检查是否达到指定时长
                    if duration:
                        elapsed = (datetime.now() - self.start_time).total_seconds()
                        if elapsed >= duration:
                            print(f"\n已达到指定时长 {duration} 秒")
                            break
            
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(f"\n录制完成！")
            print(f"总大小：{self.total_bytes / 1024 / 1024:.2f} MB")
            print(f"总时长：{elapsed:.1f} 秒")
            print(f"平均速率：{self.total_bytes / elapsed / 1024:.1f} KB/s")
            print(f"保存位置：{self.output_file}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"请求错误：{e}")
            return False
        except Exception as e:
            print(f"发生错误：{e}")
            return False
        finally:
            self.is_recording = False
    
    def record_with_urllib3(self, duration: int = None):
        """
        使用 urllib3 库录制音频流（备选方案）
        
        Args:
            duration: 录制时长（秒），None 表示无限录制
        """
        try:
            import urllib3
        except ImportError:
            print("错误：需要安装 urllib3 库")
            print("运行：pip install urllib3")
            return False
        
        print(f"开始连接到音频流：{self.stream_url}")
        
        try:
            http = urllib3.PoolManager()
            response = http.request(
                'GET',
                self.stream_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                },
                preload_content=False,
                timeout=urllib3.Timeout(connect=30, read=30)
            )
            
            print(f"连接成功！状态码：{response.status}")
            print(f"内容类型：{response.headers.get('content-type', 'unknown')}")
            print(f"开始录制到：{self.output_file}")
            
            self.is_recording = True
            self.start_time = datetime.now()
            self.total_bytes = 0
            
            with open(self.output_file, 'wb') as f:
                while True:
                    if not self.is_recording:
                        break
                    
                    chunk = response.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    self.total_bytes += len(chunk)
                    
                    # 每 10MB 显示一次进度
                    if self.total_bytes % (10 * 1024 * 1024) < self.chunk_size:
                        elapsed = (datetime.now() - self.start_time).total_seconds()
                        rate = self.total_bytes / elapsed if elapsed > 0 else 0
                        print(f"已录制：{self.total_bytes / 1024 / 1024:.2f} MB, "
                              f"时长：{elapsed:.1f}s, 速率：{rate/1024:.1f} KB/s")
                    
                    # 检查是否达到指定时长
                    if duration:
                        elapsed = (datetime.now() - self.start_time).total_seconds()
                        if elapsed >= duration:
                            print(f"\n已达到指定时长 {duration} 秒")
                            break
            
            response.release_conn()
            
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(f"\n录制完成！")
            print(f"总大小：{self.total_bytes / 1024 / 1024:.2f} MB")
            print(f"总时长：{elapsed:.1f} 秒")
            print(f"保存位置：{self.output_file}")
            
            return True
            
        except Exception as e:
            print(f"发生错误：{e}")
            return False
        finally:
            self.is_recording = False
    
    def stop(self):
        """停止录制"""
        self.is_recording = False
        print("正在停止录制...")


def find_stream_url_manually():
    """提供手动查找流 URL 的指导"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           如何手动查找 LiveATC 的真实音频流 URL              ║
╠══════════════════════════════════════════════════════════════╣
║ 由于 LiveATC.net 使用 Cloudflare 保护，且流媒体服务器域名    ║
║ (如 a1.liveatc.net) 在某些网络环境下无法解析，建议按以下     ║
║ 步骤操作：                                                   ║
║                                                              ║
║ 方法一：从浏览器获取流 URL                                   ║
║ ───────────────────────────────────────────────────────────  ║
║ 1. 在浏览器中打开：https://www.liveatc.net/hlisten.php?      ║
║                    mount=rpll&icao=rpll                      ║
║                                                              ║
║ 2. 按 F12 打开开发者工具                                     ║
║                                                              ║
║ 3. 切换到 "Network" (网络) 标签                              ║
║                                                              ║
║ 4. 刷新页面并开始播放音频                                    ║
║                                                              ║
║ 5. 在网络请求列表中查找：                                    ║
║    - 类型为 "media" 的请求                                   ║
║    - 或持续传输数据的请求                                    ║
║    - 通常是以 http:// 开头的流媒体 URL                       ║
║                                                              ║
║ 6. 右键点击该请求 -> Copy -> Copy link address               ║
║                                                              ║
║ 7. 将复制的 URL 用于本脚本：                                 ║
║    python liveatc_recorder.py --url <复制的 URL>             ║
║                     --output rpll_audio.mp3                  ║
║                                                              ║
║ 方法二：使用其他工具                                         ║
║ ───────────────────────────────────────────────────────────  ║
║ 如果上述方法不可行，可以尝试：                               ║
║ - 使用 streamlink 工具                                       ║
║ - 使用 VLC 媒体播放器打开网页并获取流地址                    ║
║ - 使用 ffmpeg 直接录制                                       ║
║                                                              ║
║ 注意：                                                       ║
║ - LiveATC 的流 URL 可能因地区和时间而变化                    ║
║ - 某些网络环境可能需要代理才能访问流服务器                   ║
╚══════════════════════════════════════════════════════════════╝
    """)


def main():
    parser = argparse.ArgumentParser(
        description='LiveATC 实时音频转存工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 无限录制（按 Ctrl+C 停止）
  python liveatc_recorder.py --url "http://example.com:8000/stream" --output audio.mp3
  
  # 录制 300 秒
  python liveatc_recorder.py --url "http://example.com:8000/stream" --output audio.mp3 --duration 300
  
  # 使用 urllib3 作为后端
  python liveatc_recorder.py --url "http://example.com:8000/stream" --output audio.mp3 --backend urllib3
  
  # 查看如何手动获取流 URL
  python liveatc_recorder.py --help-find-url
        """
    )
    
    parser.add_argument('--url', '-u', type=str, help='音频流 URL (Icecast/Shoutcast 流)')
    parser.add_argument('--output', '-o', type=str, default=None, 
                       help='输出文件名 (默认：liveatc_YYYYMMDD_HHMMSS.mp3)')
    parser.add_argument('--duration', '-d', type=int, default=None,
                       help='录制时长（秒），不指定则无限录制')
    parser.add_argument('--backend', '-b', choices=['requests', 'urllib3'], default='requests',
                       help='使用的 HTTP 后端库 (默认：requests)')
    parser.add_argument('--chunk-size', type=int, default=8192,
                       help='读取块大小 (默认：8192 字节)')
    parser.add_argument('--help-find-url', action='store_true',
                       help='显示如何手动查找流 URL 的说明')
    
    args = parser.parse_args()
    
    # 显示如何查找 URL
    if args.help_find_url:
        find_stream_url_manually()
        return 0
    
    # 检查是否提供了 URL
    if not args.url:
        print("错误：必须提供音频流 URL")
        print("使用 --help 查看使用说明")
        print("或使用 --help-find-url 查看如何获取 URL")
        return 1
    
    # 生成默认输出文件名
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"liveatc_{timestamp}.mp3"
    
    # 确保输出目录存在
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("LiveATC 实时音频转存工具")
    print("=" * 60)
    
    # 创建录制器
    recorder = AudioRecorder(
        stream_url=args.url,
        output_file=args.output,
        chunk_size=args.chunk_size
    )
    
    # 选择后端开始录制
    if args.backend == 'requests':
        success = recorder.record_with_requests(duration=args.duration)
    else:
        success = recorder.record_with_urllib3(duration=args.duration)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
