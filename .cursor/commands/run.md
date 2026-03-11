# run

启动 悟空 Wukong 项目。请在终端中依次执行以下命令：

## 1. 创建虚拟环境（如果不存在）

Windows PowerShell:
```powershell
if (-not (Test-Path ".venv")) { python -m venv .venv }
```

## 2. 激活虚拟环境并安装依赖

Windows PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1; pip install -e .
```

## 3. 启动项目

```powershell
wukong
```

---

如果是 Linux/Mac，使用以下命令：
```bash
# 创建虚拟环境
[ ! -d ".venv" ] && python3 -m venv .venv

# 激活并安装
source .venv/bin/activate && pip install -e .

# 启动
wukong
```
