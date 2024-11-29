from flask import Flask, request, jsonify, send_file
import requests
from config import Config
import json
import os
from pathlib import Path
import time
from io import BytesIO

app = Flask(__name__)

# 工作流目录
WORKFLOWS_DIR = Path(__file__).parent / 'workflows'
WORKFLOWS_DIR.mkdir(exist_ok=True)

def get_comfyui_url(endpoint):
    """构建ComfyUI API URL"""
    url = f"{Config.COMFYUI_BASE_URL}/{endpoint.lstrip('/')}"
    print(f"ComfyUI URL: {url}")  # 打印实际使用的URL
    return url

def load_workflow(workflow_name):
    """加载指定的工作流文件"""
    workflow_path = WORKFLOWS_DIR / f"{workflow_name}.json"
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow {workflow_name} not found")
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.route('/api/test_comfy', methods=['GET'])
def test_comfy_connection():
    """测试ComfyUI连接"""
    try:
        url = get_comfyui_url('/system_stats')
        print(f"Testing ComfyUI connection at: {url}")
        response = requests.get(url)
        response.raise_for_status()
        return jsonify({
            'status': 'success',
            'comfyui_url': url,
            'response': response.json()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'comfyui_url': url,
            'error': str(e)
        }), 500

@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    """列出所有可用的工作流"""
    workflows = [f.stem for f in WORKFLOWS_DIR.glob('*.json')]
    return jsonify({
        'workflows': workflows
    })

@app.route('/api/workflow/<workflow_name>', methods=['POST'])
def run_workflow(workflow_name):
    """运行指定的工作流"""
    try:
        # 打印请求信息用于调试
        print(f"Received request for workflow: {workflow_name}")
        print(f"Request Content-Type: {request.headers.get('Content-Type')}")
        print(f"Request body: {request.get_data(as_text=True)}")
        print(f"ComfyUI Base URL: {Config.COMFYUI_BASE_URL}")
        
        # 检查请求体
        if not request.is_json:
            return jsonify({
                'error': 'Request must be JSON. Check Content-Type header and request body format.'
            }), 400
            
        # 加载基础工作流
        workflow_data = load_workflow(workflow_name)
        
        # 获取请求中的参数
        request_data = request.get_json()
        print(f"Parsed request data: {request_data}")
        
        # 如果请求中包含参数，则更新工作流参数
        if request_data:
            for node_id, node_data in request_data.items():
                if node_id in workflow_data['prompt']:
                    # 如果是inputs对象，直接更新inputs中的参数
                    if 'inputs' in node_data:
                        workflow_data['prompt'][node_id]['inputs'].update(node_data['inputs'])
                    else:
                        # 如果直接提供参数，则更新inputs
                        workflow_data['prompt'][node_id]['inputs'].update(node_data)
        
        # 打印最终的工作流数据
        print(f"Final workflow data: {json.dumps(workflow_data, indent=2)}")
        
        try:
            # 1. 先提交客户端ID
            client_id = f"my-api-{int(time.time())}"
            
            # 2. 提交工作流到prompt接口
            prompt_url = get_comfyui_url('/prompt')
            print(f"Sending workflow to prompt endpoint: {prompt_url}")
            
            prompt_response = requests.post(
                prompt_url,
                json={
                    "prompt": workflow_data["prompt"],
                    "client_id": client_id
                },
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"Prompt Response Status: {prompt_response.status_code}")
            print(f"Prompt Response Content: {prompt_response.text}")
            
            if prompt_response.status_code == 200:
                prompt_data = prompt_response.json()
                return jsonify({
                    'status': 'success',
                    'prompt_id': prompt_data.get('prompt_id'),
                    'node_errors': prompt_data.get('node_errors'),
                    'error': prompt_data.get('error'),
                    'client_id': client_id
                })
            else:
                return jsonify({
                    'error': 'Failed to submit workflow',
                    'status_code': prompt_response.status_code,
                    'response': prompt_response.text
                }), 502
                
        except requests.exceptions.RequestException as e:
            return jsonify({
                'error': f'Failed to communicate with ComfyUI: {str(e)}',
                'exception_type': type(e).__name__
            }), 502
            
    except json.JSONDecodeError as e:
        return jsonify({
            'error': f'Invalid JSON format: {str(e)}',
            'request_data': request.get_data(as_text=True)
        }), 400
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_all_history():
    """获取所有历史记录"""
    try:
        response = requests.get(get_comfyui_url('/history'))
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'error': 'Failed to fetch history',
                'status_code': response.status_code,
                'response': response.text
            }), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/<prompt_id>', methods=['GET'])
def get_history(prompt_id):
    """获取指定prompt_id的历史记录"""
    try:
        # 构建历史记录URL
        history_url = get_comfyui_url(f'/history/{prompt_id}')
        print(f"Fetching history from: {history_url}")
        
        response = requests.get(history_url)
        print(f"History Response Status: {response.status_code}")
        print(f"History Response Content: {response.text}")
        
        if response.status_code == 200:
            history_data = response.json()
            return jsonify(history_data)
        else:
            return jsonify({
                'error': 'Failed to fetch history',
                'status_code': response.status_code,
                'response': response.text
            }), 502
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/image/<prompt_id>', methods=['GET'])
def get_image(prompt_id):
    """获取指定prompt_id生成的图片"""
    try:
        # 1. 先获取历史记录以找到图片路径
        history_url = get_comfyui_url(f'/history/{prompt_id}')
        history_response = requests.get(history_url)
        
        if history_response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch history',
                'status_code': history_response.status_code
            }), 502
            
        history_data = history_response.json()
        
        # 2. 从历史记录中提取图片信息
        if not history_data:
            return jsonify({'error': 'History not found'}), 404
            
        # 获取输出节点的数据
        outputs = history_data[prompt_id].get('outputs', {})
        if not outputs:
            return jsonify({'error': 'No outputs found in history'}), 404
            
        # 找到SaveImage节点的输出
        images = []
        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                for image_data in node_output['images']:
                    image_url = get_comfyui_url(f"/view?filename={image_data['filename']}&subfolder={image_data.get('subfolder', '')}&type=temp")
                    images.append({
                        'url': image_url,
                        'filename': image_data['filename'],
                        'subfolder': image_data.get('subfolder', ''),
                        'type': 'temp'
                    })
        
        if not images:
            return jsonify({'error': 'No images found in output'}), 404
            
        return jsonify({
            'status': 'success',
            'images': images
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow', methods=['POST'])
def submit_workflow():
    """提交工作流到ComfyUI"""
    try:
        workflow_data = request.json
        response = requests.post(
            get_comfyui_url('/api/queue'), 
            json=workflow_data
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取ComfyUI当前状态"""
    try:
        response = requests.get(get_comfyui_url('/system_stats'))
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/view_queue', methods=['GET'])
def view_queue():
    """查看当前队列状态"""
    try:
        response = requests.get(get_comfyui_url('/queue'))
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/task_status/<prompt_id>', methods=['GET'])
def check_task_status(prompt_id):
    """检查指定任务的状态，包括图片生成进度"""
    try:
        # 1. 检查队列状态
        queue_response = requests.get(get_comfyui_url('/queue'))
        if queue_response.status_code == 200:
            queue_data = queue_response.json()
            
            # 检查是否在执行队列中
            for item in queue_data.get('queue_running', []):
                if item.get('prompt_id') == prompt_id:
                    return jsonify({
                        'status': 'running',
                        'message': 'Task is currently running',
                        'execution_info': item
                    })
            
            # 检查是否在等待队列中
            for item in queue_data.get('queue_pending', []):
                if item.get('prompt_id') == prompt_id:
                    return jsonify({
                        'status': 'pending',
                        'message': 'Task is waiting in queue',
                        'queue_position': queue_data['queue_pending'].index(item) + 1
                    })
        
        # 2. 检查历史记录
        history_response = requests.get(get_comfyui_url(f'/history/{prompt_id}'))
        if history_response.status_code == 200:
            history_data = history_response.json()
            
            if not history_data:
                return jsonify({
                    'status': 'not_found',
                    'message': 'Task not found in history'
                })
            
            task_data = history_data.get(prompt_id, {})
            outputs = task_data.get('outputs', {})
            
            # 检查是否有图片输出
            for node_id, output in outputs.items():
                if 'images' in output:
                    images = []
                    for img in output['images']:
                        image_url = get_comfyui_url(f"/view?filename={img['filename']}&subfolder={img.get('subfolder', '')}&type=temp")
                        images.append({
                            'url': image_url,
                            'filename': img['filename'],
                            'subfolder': img.get('subfolder', ''),
                            'type': 'temp'
                        })
                    
                    return jsonify({
                        'status': 'completed',
                        'message': 'Image generation completed',
                        'images': images,
                        'execution_time': task_data.get('execution_time', 0),
                        'node_errors': task_data.get('node_errors', {})
                    })
            
            # 如果有历史记录但没有图片
            return jsonify({
                'status': 'processing',
                'message': 'Task is being processed',
                'execution_time': task_data.get('execution_time', 0),
                'node_errors': task_data.get('node_errors', {})
            })
        
        # 3. 如果都没有找到
        return jsonify({
            'status': 'unknown',
            'message': 'Could not determine task status',
            'queue_response': queue_response.status_code,
            'history_response': history_response.status_code
        })
        
    except Exception as e:
        print(f"Error checking task status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
