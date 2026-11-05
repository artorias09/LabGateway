# LabGateway v0.1 — protótipo para Raspberry Pi 3

## Objetivo
Alunos enviam ZIPs com `main.py`, o professor solicita a execução e consulta status e logs. A Raspberry Pi 3 será o host no futuro; eduroam e ngrok não são necessários para desenvolver ou testar localmente.

## Escopo da v0.1
- Python 3.12 e ZIP com `main.py` na raiz; arquivos permitidos: .py, .txt, .json, .csv e .md.
- Contas criadas manualmente por administrador; papéis student e teacher.
- Apenas o professor coloca projetos na fila.
- Worker separado usa Docker sem rede, sem privilégios, com filesystem read-only e limites de recursos.
- Uma execução por vez; SQLite; saída limitada; upload máximo de 2 MiB.
- Sem instalação de dependências externas, acesso a GPIO, serial, USB ou rede no código do aluno.

## Desenvolvimento no Windows (PowerShell)
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:LAB_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))").Trim()
python admin.py create-user professor teacher
python admin.py create-user grupo01 student
python app.py
```
Abra http://127.0.0.1:5001. Crie um ZIP com `main.py` (veja `examples/main.py`); envie com conta de aluno, solicite a execução como professor. Com Docker Desktop no modo Linux containers:
```powershell
docker pull python:3.12-alpine
python worker.py --once
```
Sem Docker, a execução falha com segurança: o código do aluno **não é executado no host**.

## Testes
```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py admin.py core.py store.py worker.py tests
```

## Implantação futura
Verificar Raspberry Pi OS em ARM64 (`uname -m`), memória, espaço livre, Docker e permissões dos serviços. Fazer backup do projeto do forno e **não o sobrescrever**. Configurar contas Unix separadas para web e worker. Usar HTTPS, autenticação adicional e controle de acesso antes de configurar ngrok na eduroam autorizada.

## Riscos e limitações
Docker não é garantia absoluta de isolamento para código hostil. Ainda faltam testes integrados, rate limiting, auditoria, revisão de permissões, retenção, limpeza de contêineres após timeout e recuperação de falhas. **Não expor o protótipo à internet ou a alunos reais até homologação.**

Veja [arquitetura](docs/ARCHITECTURE.md) e [roadmap](docs/ROADMAP.md).


## Preflight da Raspberry sem HDMI

Veja [roteiro de amanhã](docs/AMANHA_RASPBERRY.md) e [decisões de rede](docs/DECISOES.md). Na máquina: `bash scripts/preflight.sh`. O script é somente leitura e não altera o servidor do forno.

O conserto de timeout no worker está na branch `feature/v02-deployment-readiness` e aguarda testes reais com Docker antes de integração na main.
