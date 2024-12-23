def main(comfyui_response: str,
         lsky_upload_url: str,
         lsky_token: str) -> dict:
    """
    上传ComfyUI生成的图片到图床
    
    参数:
        comfyui_response: ComfyUI返回的响应数据，格式如：
            {
                "images": [
                    {
                        "filename": "ComfyUI_06116_.png",
                        "subfolder": "",
                        "type": "temp",
                        "url": "http://192.168.1.196:8188/view?filename=ComfyUI_06116_.png&subfolder=&type=temp"
                    }
                ],
                "status": "success"
            }
        lsky_upload_url: Lsky图床上传API地址，例如：https://pic.example.com/api/v1/upload
        lsky_token: Lsky的API Token，支持两种格式：
                   1. Bearer your-token
                   2. your-token （会自动添加Bearer前缀）
    
    返回:
        dict: 包含结果的字典，格式为：{"result": "结果字符串"}
    """
    import requests
    import json
    from io import BytesIO
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from urllib.parse import urlparse, parse_qs
    import urllib3
    
    # 禁用SSL警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 设置重试策略
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        # 处理输入数据
        try:
            if isinstance(comfyui_response, str):
                response_data = json.loads(comfyui_response)
                # 如果数据包含body字段，则使用body内的数据
                if isinstance(response_data, dict) and 'body' in response_data:
                    comfyui_data = json.loads(response_data['body'])
                else:
                    comfyui_data = response_data
            else:
                comfyui_data = comfyui_response
        except json.JSONDecodeError:
            return {"result": "Error: Invalid JSON string in comfyui_response"}

        # 1. 验证并获取图片信息
        if not comfyui_data.get('status') == 'success' or not comfyui_data.get('images'):
            return {"result": "Error: Invalid response data or no images found"}
        
        image_info = comfyui_data['images'][0]  # 获取第一张图片
        image_url = image_info['url']
        filename = image_info['filename']
        
        def clean_url(url: str) -> str:
            """
            清理URL，只保留filename参数，并确保使用正确的端口
            """
            # 移除可能存在的前缀@符号和结尾的反斜杠
            url = url.lstrip('@').rstrip('\\')
            
            parsed_url = urlparse(url)
            # 保持原始路径
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            query_params = parse_qs(parsed_url.query)
            
            if 'filename' in query_params:
                return f"{base_url}?filename={query_params['filename'][0]}"
            return url

        image_url = clean_url(image_info['url'])
        
        # 添加调试信息
        print(f"Attempting to download image from: {image_url}")
        
        # 2. 下载图片
        try:
            image_response = session.get(
                image_url,
                verify=False,
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            image_response.raise_for_status()  # 这会在状态码不是200时抛出异常
        except requests.exceptions.RequestException as e:
            return {"result": f"Error: Failed to download image - {str(e)}"}
            
        if image_response.status_code != 200:
            return {"result": f"Error: Failed to download image (Status {image_response.status_code})"}
        
        # 验证下载的内容是否为图片
        content_type = image_response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            return {"result": f"Error: Downloaded content is not an image (Content-Type: {content_type})"}
        
        image_data = image_response.content
        
        # 3. 上传到图床
        if not lsky_token.startswith('Bearer '):
            lsky_token = f'Bearer {lsky_token}'
            
        headers = {
            "Authorization": lsky_token
        }
        
        files = {
            'file': (filename, BytesIO(image_data), 'image/png')
        }
        
        upload_response = session.post(
            lsky_upload_url,
            headers=headers,
            files=files,
            verify=False,
            timeout=30
        )
        
        upload_result = upload_response.json()
        
        if not upload_result.get('status'):
            return {"result": f"Error: Upload failed - {upload_result.get('message', 'Unknown error')}"}
        
        image_url = upload_result.get('data', {}).get('links', {}).get('url')
        if not image_url:
            return {"result": "Error: No image URL in upload response"}
            
        return {"result": f"![Generated Image]({image_url})"}
        
    except Exception as e:
        return {"result": f"Error: {str(e)}"}
