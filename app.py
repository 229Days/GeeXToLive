from flask import Flask, request, jsonify, render_template
from flask_mysqldb import MySQL
from flask_cors import CORS
import redis
from flask_socketio import SocketIO, emit
import threading
import time
import uuid
import json
import logging
import sys
import const
import pyaudio
import websocket

# 初始化Flask应用
app = Flask(__name__)  # 创建一个Flask应用实例
CORS(app)  # 初始化CORS，允许跨域请求
app.config['SECRET_KEY'] = 'secret!'  # 设置Flask应用的密钥
socketio = SocketIO(app)  # 初始化SocketIO，传入Flask应用实例

# 配置MySQL数据库连接
app.config['MYSQL_HOST'] = 'localhost'  # 数据库主机地址
app.config['MYSQL_USER'] = 'root'  # 数据库用户名
app.config['MYSQL_PASSWORD'] = '123456'  # 数据库密码
app.config['MYSQL_DB'] = 'live_streaming'  # 数据库名称

mysql = MySQL(app)  # 初始化MySQL，传入Flask应用实例

# 配置Redis连接
redis_client = redis.Redis(host='localhost', port=6379, db=0)  # 连接到本地Redis服务器，默认端口是6379，使用数据库0

@app.route('/api/data', methods=['GET'])  # 定义一个路由，路径为/api/data，只接受GET请求
def get_data():
    # 尝试从Redis获取数据
    data = redis_client.get('data')  # 从Redis中获取键为'data'的值
    if data:
        return jsonify(eval(data))  # 如果Redis中有数据，将其转换为Python对象并返回为JSON格式
    else:
        # 如果Redis中没有数据，从MySQL获取数据
        cursor = mysql.connection.cursor()  # 创建一个数据库游标
        cursor.execute("SELECT * FROM your_table")  # 执行SQL查询，从your_table表中选择所有数据
        data = cursor.fetchall()  # 获取所有查询结果
        cursor.close()  # 关闭游标
        
        # 将数据存储到Redis
        redis_client.set('data', str(data))  # 将查询结果转换为字符串并存储到Redis中，键为'data'
        
        return jsonify(data)  # 返回查询结果为JSON格式


# 设置音频参数
FORMAT = pyaudio.paInt16  # 音频格式
CHANNELS = 1  # 声道数
RATE = 16000  # 采样率
CHUNK = int(RATE * 2 / 1000 * 160)  # 160ms的数据块大小

# 初始化pyaudio
p = pyaudio.PyAudio()

# 打开麦克风流
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

# 发送开始参数到WebSocket服务器
def send_start_params(ws):
    req = {
        "type": "START",
        "data": {
            "appid": const.APPID,
            "appkey": const.APPKEY,
            "dev_pid": const.DEV_PID,
            "cuid": "cuid_1",
            "sample": 16000,
            "format": "pcm",
            "lm_id": "21684"
        }
    }
    body = json.dumps(req)  # 将请求对象转换为JSON字符串
    ws.send(body, websocket.ABNF.OPCODE_TEXT)  # 发送JSON字符串到WebSocket服务器

# 发送音频数据到WebSocket服务器
def send_audio(ws):
    while True:
        data = stream.read(CHUNK)  # 从麦克风读取音频数据
        ws.send(data, websocket.ABNF.OPCODE_BINARY)  # 发送音频数据到WebSocket服务器
        time.sleep(160 / 1000.0)  # 暂停160毫秒

# 发送结束标志到WebSocket服务器
def send_finish(ws):
    req = {
        "type": "FINISH"
    }
    body = json.dumps(req)  # 将请求对象转换为JSON字符串
    ws.send(body, websocket.ABNF.OPCODE_TEXT)  # 发送JSON字符串到WebSocket服务器

# 发送取消标志到WebSocket服务器
def send_cancel(ws):
    req = {
        "type": "CANCEL"
    }
    body = json.dumps(req)  # 将请求对象转换为JSON字符串
    ws.send(body, websocket.ABNF.OPCODE_TEXT)  # 发送JSON字符串到WebSocket服务器

# WebSocket连接打开后的回调函数
def on_open(ws):
    def run(*args):
        send_start_params(ws)  # 发送开始参数
        send_audio(ws)  # 发送音频数据
        send_finish(ws)  # 发送结束标志
    threading.Thread(target=run).start()  # 在新线程中运行

# WebSocket接收到消息后的回调函数
def on_message(ws, message):
    try:
        message = json.loads(message)  # 将JSON字符串转换为Python对象
        if "result" in message:
            check_and_print_message(message["type"], message["result"])  # 检查并打印消息
    except json.JSONDecodeError as e:
        logging.error("Error decoding JSON message: " + str(e))  # 记录JSON解码错误

# WebSocket发生错误后的回调函数
def on_error(ws, error):
    logging.error("error: " + str(error))  # 记录错误信息

# WebSocket连接关闭后的回调函数
def on_close(ws):
    logging.info("ws close ...")  # 记录关闭信息
    socketio.emit('close')  # 向所有SocketIO客户端发送关闭事件

# 检查并打印消息
def check_and_print_message(message, result):
    if any(char in message for char in ["FIN_TEXT"]):
        print(result)  # 打印结果
        socketio.emit('result', result)  # 向所有SocketIO客户端发送结果事件

# Flask路由，渲染首页
@app.route('/')
def index():
    return render_template('index.html')  # 渲染index.html模板

# SocketIO事件处理，处理开始事件
@socketio.on('start')
def handle_start():
    uri = const.URI + "?sn=" + str(uuid.uuid1())  # 生成WebSocket URI，包含唯一标识符
    logging.info("uri is " + uri)  # 记录URI信息
    const.ws = websocket.WebSocketApp(uri,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)  # 创建WebSocket应用实例
    ws_thread = threading.Thread(target=const.ws.run_forever)  # 创建线程，用于运行WebSocket
    ws_thread.start()  # 启动线程

# SocketIO事件处理，处理停止事件
@socketio.on('stop')
def handle_stop():
    if const.ws:
        socketio.emit('close')  # 向所有SocketIO客户端发送关闭事件
        const.ws.close()  # 关闭WebSocket连接
        const.ws = None  # 重置ws对象

# 接收前端传来的关键词
@socketio.on('add_keyword')
def handle_add_keyword(data):
    keyword = data['keyword']  # 从数据中获取关键词
    const.keywords.append(keyword)  # 将关键词添加到常量模块的关键词列表中
    print(f'添加关键词: {keyword}')  # 打印添加的关键词
    emit('keyword_added', {'keyword': keyword})  # 向所有SocketIO客户端发送关键词添加事件

# 主函数，启动应用
if __name__ == "__main__":
    socketio.run(app, debug=True)  # 运行SocketIO应用，开启调试模式



# if __name__ == '__main__':
#     app.run(debug=True)  # 如果当前脚本为主程序，则运行Flask应用，开启调试模式
