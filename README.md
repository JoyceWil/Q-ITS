<h2> Q-ITS 量子增强智能导学系统 </h2> 
借助中国电信天衍量子云计算平台实现的量子增强智能导学系统

```sh
# Create environment
conda create -n q_its python=3.12 
conda activate q_its

# Install packages
pip install -r requirements.txt
```

```aiignore
# Setting of Dify Platform
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"
DIFY_API_KEY = "" 
```

```sh
# Launching
python src/Flask/app.py
```

```aiignore
# View
See http://127.0.0.1:5000
```
