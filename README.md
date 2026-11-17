# LabGateway v0.1 — protótipo para Raspberry Pi 3

**Status: não homologado para exposição pública ou execução de código desconhecido.** Código disponível para testes locais. Requer Docker para executar projetos dos alunos.

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


## Reaproveitamento do forno (recomendado)\n\nO projeto **não** reconfigura eduroam, roteamento, duas interfaces Wi-Fi, ngrok ou o serviço do forno. A auditoria somente leitura em `scripts/audit_forno_reuse.sh` identifica o que já está operando. Consulte [REAPROVEITAMENTO_FORNO.md](docs/REAPROVEITAMENTO_FORNO.md). A porta 5000 continua reservada para o forno e a aplicação nova usa 5001. Docker é necessário para executar código de alunos; não será instalado nem forçado no OS antigo sem diagnóstico.\n\n## Preflight da Raspberry sem HDMI

Veja [roteiro de amanhã](docs/AMANHA_RASPBERRY.md) e [decisões de rede](docs/DECISOES.md). Na máquina: `bash scripts/preflight.sh`. O script é somente leitura e não altera o servidor do forno.

O conserto de timeout no worker está na branch `feature/v02-deployment-readiness` e aguarda testes reais com Docker antes de integração na main.


## Validação técnica de projetos

A versão em desenvolvimento identifica projetos Python, C, C++ e ESP32/Arduino.

- Python: executado em contêiner isolado.
- C e C++: compilados com avisos habilitados e executados em contêiner isolado.
- ESP32/Arduino: aceitos e identificados; a toolchain específica ainda não é executada automaticamente.
- O professor pode baixar o projeto recebido como ZIP usando o título informado pelo aluno como nome do arquivo.

Antes de validar C/C++ na Raspberry, construa uma vez a imagem local:

```bash
sudo bash scripts/prepare_runners.sh
```

O runner não tem rede durante a avaliação e o código não é executado diretamente no host.


## Dados experimentais

A interface possui uma área separada para registrar resultados experimentais. Cada envio pode ser associado a um projeto e inclui nome do ensaio, descrição, unidades e arquivo CSV ou JSON.

O servidor registra no SQLite o responsável, projeto relacionado, formato, número de registros, nomes das colunas, caminho do arquivo e data do envio. O arquivo original permanece armazenado para download e a interface mostra uma prévia de até 20 registros.

Essa estrutura deixa o banco pronto para uma evolução futura em que bancadas ou nós de rede alimentem os mesmos registros automaticamente.


## Aquisição automática com ESP32

A v0.5 adiciona aquisição contínua para as estações ambientais. O código de cada grupo continua executando na própria ESP32 e inclui o cliente padrão em `esp32/LabGateway.h`.

Fluxo:

```text
ESP32 -> HTTPS -> /api/v1/measurements -> SQLite -> Monitoramento
```

Cada pacote identifica a estação e envia um conjunto livre de variáveis numéricas. O servidor registra horário de aquisição, horário de recebimento, variável, valor e unidade. As estações podem ter sensores diferentes sem alterar o esquema do servidor.

Exemplo de pacote:

```json
{
  "station": "grupo_01",
  "name": "Estacao 01",
  "group": "Grupo 01",
  "data": {
    "temperatura": 24.7,
    "umidade": 61.2
  },
  "units": {
    "temperatura": "C",
    "umidade": "%"
  }
}
```

O endpoint exige o cabeçalho `X-LabGateway-Token`. O token é criado no servidor durante instalação ou atualização e fica em `/etc/labgateway/web.env` como `LAB_INGEST_TOKEN`.

O professor acessa **Monitoramento** para selecionar uma estação, verificar a última comunicação, quantidade de medições, período de aquisição e curvas. A página da estação consulta os últimos pontos e atualiza o gráfico a cada 5 segundos.

Para a atividade das estações ambientais, recomenda-se começar com intervalo de transmissão de 30 segundos e ajustar conforme a dinâmica dos sensores. O intervalo da ESP e a atualização visual do dashboard são independentes.

Esta versão usa arquitetura centralizada ESP32 -> servidor. Uma rede mesh entre nós pode ser adicionada posteriormente sem alterar o modelo central de armazenamento.
