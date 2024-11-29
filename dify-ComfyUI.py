def main(prompt: str, workflow: str, nodeid: str, 
         comfyui_base_url: str,
         lsky_upload_url: str,
         lsky_token: str,
         timeout_seconds: str = "600") -> dict:  # 默认10分钟超时
    """
    调用ComfyUI生成图片并上传到图床
    
    参数示例：
        prompt: "一只可爱的猫"
        workflow: "workflow-api"
        nodeid: "4"
        comfyui_base_url: "http://localhost:5000"
        lsky_upload_url: "http://image-host:2222/api/v1/upload"
        lsky_token: "Bearer token"
        timeout_seconds: "600"  # 总超时时间（秒），默认10分钟
    """
    import json
    import requests
    import time
    from io import BytesIO
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    # 设置重试策略
    retry_strategy = Retry(
        total=6,  # 增加重试次数
        backoff_factor=2,  # 增加重试等待时间
        status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
        allowed_methods=["HEAD", "GET", "POST"]  # 允许重试的HTTP方法
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        # 1. 构建完整的工作流URL和请求数据
        workflow_url = f"{comfyui_base_url}/api/workflow/{workflow}"
        
        # 构建节点输入数据
        node_inputs = {
            nodeid: {
                "inputs": {
                    "text": prompt
                }
            }
        }
        
        try:
            workflow_response = session.post(workflow_url, json=node_inputs, verify=False, timeout=60)  # 增加超时时间
            workflow_result = workflow_response.json()
            
            if 'prompt_id' not in workflow_result:
                return {
                    "result": f"Error: Failed to start workflow: {workflow_response.text}"
                }
                
            prompt_id = workflow_result['prompt_id']
            print(f"Successfully started workflow with prompt_id: {prompt_id}")  # 添加日志
            
        except requests.exceptions.Timeout:
            return {
                "result": "Error: Workflow request timed out after 60 seconds"
            }
        except Exception as e:
            return {
                "result": f"Error starting workflow: {str(e)}"
            }

        # 2. 循环检查状态
        status_url = f"{comfyui_base_url}/api/task_status/{prompt_id}"
        start_time = time.time()
        timeout_seconds = int(timeout_seconds)
        check_interval = 5  # 每5秒检查一次
        last_status = None
        
        while True:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # 检查是否超过总时长
            if elapsed_time > timeout_seconds:
                return {
                    "result": f"Error: Generation timed out after {int(elapsed_time)} seconds"
                }
                
            try:
                status_response = session.get(status_url, verify=False, timeout=40)
                status_data = status_response.json()
                current_status = status_data.get('status')
                
                # 只在状态变化时打印日志
                if current_status != last_status:
                    print(f"Status check at {int(elapsed_time)}s: {current_status}")
                    if 'message' in status_data:
                        print(f"Message: {status_data['message']}")
                    last_status = current_status
                
                if current_status == 'completed':
                    print(f"Task completed successfully in {int(elapsed_time)} seconds")
                    break
                elif current_status == 'failed':
                    return {
                        "result": f"Error: Generation failed: {status_data.get('message', 'Unknown error')}"
                    }
                elif current_status == 'error':
                    return {
                        "result": f"Error: {status_data.get('message', 'Unknown error')}"
                    }
                elif current_status == 'unknown':
                    print(f"Warning: Task status unknown, will keep checking")
                elif current_status == 'pending':
                    queue_position = status_data.get('queue_position', 'unknown')
                    print(f"Task is pending in queue, position: {queue_position}")
                elif current_status == 'running':
                    if 'execution_info' in status_data:
                        print(f"Task is running: {status_data['execution_info']}")
                
                time.sleep(check_interval)
                
            except requests.exceptions.Timeout:
                print(f"Status check timeout at {int(elapsed_time)}s, will retry...")
                time.sleep(10)  # 超时后等待更长时间
                continue
            except Exception as e:
                print(f"Status check error: {str(e)}")
                return {
                    "result": f"Error checking status: {str(e)}"
                }
                
        # 3. 获取图片信息
        image_info_url = f"{comfyui_base_url}/api/image/{prompt_id}"
        try:
            image_info_response = session.get(image_info_url, verify=False, timeout=60)  # 增加超时时间
            image_info_data = image_info_response.json()
            print(f"Image info response: {json.dumps(image_info_data)}")  # 添加日志
            
            if image_info_data.get('status') != 'success' or not image_info_data.get('images'):
                return {
                    "result": f"Error: Failed to get image info: {json.dumps(image_info_data)}"
                }
            
            # 获取完整URL并处理
            full_url = image_info_data['images'][0]['url']
            # 只保留&之前的部分
            image_url = full_url.split('&')[0]
            print(f"Image URL: {image_url}")  # 添加日志
            
        except requests.exceptions.Timeout:
            return {
                "result": "Error: Image info request timed out"
            }
        except Exception as e:
            return {
                "result": f"Error getting image info: {str(e)}"
            }
        
        # 4. 下载图片
        try:
            image_response = session.get(image_url, verify=False, timeout=60)  # 增加超时时间
            if image_response.status_code != 200:
                return {
                    "result": f"Error downloading image: Status code {image_response.status_code}, URL: {image_url}"
                }
            image_data = image_response.content
            print(f"Successfully downloaded image, size: {len(image_data)} bytes")  # 添加日志
            
        except requests.exceptions.Timeout:
            return {
                "result": "Error: Image download timed out"
            }
        except Exception as e:
            return {
                "result": f"Error downloading image: {str(e)}"
            }

        # 5. 上传到兰空图床
        try:
            headers = {
                "Authorization": f"Bearer {lsky_token}"
            }
            
            files = {
                'file': ('image.png', BytesIO(image_data), 'image/png')
            }
            
            upload_response = session.post(
                lsky_upload_url,
                headers=headers,
                files=files,
                verify=False,
                timeout=60  # 增加超时时间
            )
            
            upload_result = upload_response.json()
            print(f"Upload response: {json.dumps(upload_result)}")  # 添加日志
            
            if not upload_result.get('status'):
                return {
                    "result": f"Error uploading to image host: {upload_result.get('message', 'Unknown error')}"
                }
            
            # 提取图片URL和生成markdown
            image_url = upload_result['data']['links']['url']
            markdown = f"![image]({image_url})"
            
            print(f"Successfully uploaded image: {image_url}")  # 添加日志
            
            # 直接返回markdown字符串
            return {
                "result": markdown
            }
            
        except requests.exceptions.Timeout:
            return {
                "result": "Error: Image upload timed out"
            }
        except Exception as e:
            return {
                "result": f"Error uploading to image host: {str(e)}"
            }

    except Exception as e:
        return {
            "result": f"Error: {str(e)}"
        }
