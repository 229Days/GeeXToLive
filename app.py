from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_cors import CORS
import redis

app = Flask(__name__)
CORS(app)

# MySQL配置
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '123456'
app.config['MYSQL_DB'] = 'live_streaming'

mysql = MySQL(app)

# Redis配置
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@app.route('/api/data', methods=['GET'])
def get_data():
    # 尝试从Redis获取数据
    data = redis_client.get('data')
    if data:
        return jsonify(eval(data))  # 将字符串转换为Python对象
    else:
        # 从MySQL获取数据
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM your_table")
        data = cursor.fetchall()
        cursor.close()
        
        # 将数据存储到Redis
        redis_client.set('data', str(data))
        
        return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
