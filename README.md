# LabGateway v0.5

Servidor de projetos, dados experimentais e aquisição automática para instrumentação com ESP32.

## Instrução para a turma

O procedimento é o mesmo para todos os projetos, mesmo que cada grupo use sensores diferentes.

O aluno recebe o arquivo `LabGateway.h` já configurado pelo responsável pela atividade.

### 1. Coloque o arquivo LabGateway.h junto do código

### 2. No começo do código, cole

```cpp
#include "LabGateway.h"
```

### 3. No loop, depois da leitura dos sensores, cole

```cpp
LabGateway.enviar(
  COLOQUE_VARIAVEL_1_AQUI,
  COLOQUE_VARIAVEL_2_AQUI
);
```

### 4. Troque somente as lacunas

Se as variáveis do projeto forem `temperatura` e `umidade`:

```cpp
LabGateway.enviar(
  temperatura,
  umidade
);
```

Pronto.

Se houver uma variável:

```cpp
LabGateway.enviar(temperatura);
```

Se houver três:

```cpp
LabGateway.enviar(temperatura, umidade, pressao);
```

A mesma chamada aceita 1, 2, 3 ou mais medições.

## O que o aluno não precisa configurar

O aluno não configura intervalo de transmissão, número do grupo, nome da estação, URL, token, JSON, HTTP, endpoint, banco de dados ou dashboard.

A biblioteca:

- identifica automaticamente cada ESP32 pelo chip;
- transforma os valores em `variavel_1`, `variavel_2`, `variavel_3` e assim por diante;
- limita automaticamente a transmissão para uma aquisição a cada 30 segundos;
- não bloqueia o loop entre os envios;
- só atualiza o relógio de transmissão quando o servidor confirma o recebimento;
- monta o pacote;
- autentica;
- envia ao servidor.

O aluno pode deixar `LabGateway.enviar(...)` dentro do `loop()`. Mesmo que o loop execute milhares de vezes, a biblioteca só transmite quando o intervalo configurado for atingido.

O intervalo padrão é definido em `LABGATEWAY_INTERVALO_MS` dentro da configuração distribuída pela equipe. O padrão atual é 30 segundos. Isso pode ser alterado centralmente antes de entregar o arquivo à turma sem mudar o procedimento dos alunos.

## Fluxo

```text
codigo do aluno
      |
LabGateway.enviar(...)
      |
controle automatico do intervalo
      |
HTTPS
      |
Raspberry Pi
      |
Flask
      |
SQLite
      |
Monitoramento
```

O endpoint de aquisição é `POST /api/v1/measurements`. O servidor armazena cada posição como uma série temporal independente. O professor acompanha as estações pela página Monitoramento.

A atualização visual do gráfico é independente do intervalo de aquisição.

## Configuração feita pela equipe

Antes de distribuir `LabGateway.h`, o responsável configura:

```cpp
#define LABGATEWAY_URL "https://ENDERECO-DO-SERVIDOR"
#define LABGATEWAY_TOKEN "TOKEN-DO-SERVIDOR"
#define LABGATEWAY_INTERVALO_MS 30000UL
```

Esses dados não fazem parte do passo a passo do aluno.

## Dados experimentais

O sistema também mantém o envio manual de CSV e JSON e a associação de dados a projetos.

## Projetos

O fluxo de envio e validação de projetos continua disponível. A aquisição das ESP32 é independente da execução de código na Raspberry.

## Testes

```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py admin.py core.py store.py worker.py tests
```

## Implantação

A aplicação usa a porta 5001. O serviço do forno permanece separado na porta 5000.

O servidor usa `LAB_INGEST_TOKEN` em `/etc/labgateway/web.env`. O valor correspondente deve ser colocado no `LabGateway.h` distribuído para a atividade.
