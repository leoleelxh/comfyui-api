import os
from dotenv import load_dotenv

# 尝试加载.env文件，但如果不存在也不会报错
load_dotenv(override=True)

class Config:
    # ComfyUI服务地址，优先使用环境变量，否则使用默认值
    COMFYUI_BASE_URL = os.environ.get('COMFYUI_BASE_URL', 'http://localhost:8188')
    
    # Flask配置
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
