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
        # 将字符串转换为字典
        try:
            if isinstance(comfyui_response, str):
                comfyui_response = json.loads(comfyui_response)
        except json.JSONDecodeError:
            return {"result": "Error: Invalid JSON string in comfyui_response"}

        # 1. 验证并获取图片信息
        if not comfyui_response.get('status') == 'success' or not comfyui_response.get('images'):
            return {"result": "Error: Invalid response data or no images found"}
        
        image_info = comfyui_response['images'][0]
        image_url = image_info['url']
        filename = image_info['filename']
        
        # 处理URL，移除多余的参数
        parsed_url = urlparse(image_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        query_params = parse_qs(parsed_url.query)
        
        if 'filename' in query_params:
            image_url = f"{base_url}?filename={query_params['filename'][0]}"
        
        # 2. 下载图片
        image_response = session.get(image_url, verify=False, timeout=30)
        if image_response.status_code != 200:
            return {"result": f"Error: Failed to download image (Status {image_response.status_code})"}
        
        image_data = image_response.content
        
        # 3. 上传到图床
        # 处理token格式
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
        
        # 返回markdown格式的图片链接
        image_url = upload_result.get('data', {}).get('links', {}).get('url')
        if not image_url:
            return {"result": "Error: No image URL in upload response"}
            
        return {"result": f"![Generated Image]({image_url})"}
        
    except Exception as e:
        return {"result": f"Error: {str(e)}"}
