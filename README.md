# ComfyUI API Service

这是一个基于Flask的ComfyUI API服务，提供了便捷的REST API接口来与ComfyUI进行交互。

## 功能特性

- 支持配置ComfyUI服务地址
- 提供工作流提交接口
- 支持查询历史记录
- 支持查询系统状态
- 支持查看队列状态

## 安装

1. 克隆项目到本地
2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置

可以通过环境变量或.env文件配置以下参数：

- COMFYUI_BASE_URL: ComfyUI服务地址（默认：http://127.0.0.1:8188）
- FLASK_DEBUG: 调试模式（默认：True）
- FLASK_HOST: 服务监听地址（默认：0.0.0.0）
- FLASK_PORT: 服务端口（默认：5000）

## API接口

### 提交工作流
- POST /api/workflow
- 请求体：ComfyUI工作流JSON数据

### 获取历史记录
- GET /api/history

### 获取系统状态
- GET /api/status

### 查看队列状态
- GET /api/view_queue

## 运行

```bash
python app.py
```
