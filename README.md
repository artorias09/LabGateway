# LabGateway v0.5

Servidor de projetos, dados experimentais e aquisição automática para instrumentação com ESP32.

## Integração das ESP32

A integração foi feita para ser igual em todos os projetos. Cada grupo mantém o próprio código, sensores e lógica de aquisição.

O aluno recebe o arquivo `LabGateway.h` já configurado pelo responsável pela atividade e copia este bloco para o projeto:

```cpp
#include "LabGateway.h"

void enviarParaLabGateway() {
  LabGateway.enviar(
    COLOQUE_VARIAVEL_1_AQUI,
    COLOQUE_VARIAVEL_2_AQUI
  );
}
```

O aluno troca somente as lacunas pelos nomes das variáveis que já existem no código.

Exemplo:

```cpp
LabGateway.enviar(
  temperatura,
  umidade
);
```

Se o projeto tiver outra quantidade de medições, a mesma chamada aceita 1, 2, 3 ou mais variáveis:

```cpp
LabGateway.enviar(temperatura);
LabGateway.enviar(temperatura, umidade);
LabGateway.enviar(temperatura, umidade, pressao);
```

A biblioteca registra as posições como `variavel_1`, `variavel_2`, `variavel_3` e assim por diante. O servidor não precisa conhecer previamente os sensores usados pelo grupo.

Cada ESP32 é identificada automaticamente pelo identificador único do chip. Portanto, o aluno não precisa informar número do grupo, nome da estação, URL, token, JSON, endpoint ou banco de dados no código da atividade.

O responsável pela atividade configura `LABGATEWAY_URL` e `LABGATEWAY_TOKEN` no arquivo distribuído aos alunos. Esses detalhes ficam fora do procedimento de integração do aluno.

Fluxo:

```text
codigo do aluno
      |
LabGateway.enviar(...)
      |
LabGateway.h
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

O endpoint de aquisição é `POST /api/v1/measurements`. O servidor armazena cada variável como uma série temporal independente e o professor acompanha as estações pela página Monitoramento.

A atualização do gráfico e o intervalo de aquisição são independentes. O intervalo de envio deve ser definido conforme a atividade e a dinâmica dos sensores.

## Dados experimentais

Também é possível registrar resultados manualmente em CSV ou JSON e associá-los a um projeto. O professor pode visualizar uma prévia e baixar o arquivo original.

## Projetos

O sistema mantém o fluxo de envio de projetos e validação já existente. A aquisição automática das ESP32 é uma camada adicional e não exige que o código do aluno seja executado na Raspberry.

## Testes

```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py admin.py core.py store.py worker.py tests
```

## Implantação

A aplicação usa a porta 5001. O serviço do forno permanece separado na porta 5000 e não deve ser alterado.

A aquisição automática usa o token `LAB_INGEST_TOKEN` definido em `/etc/labgateway/web.env`. O arquivo `LabGateway.h` entregue à turma deve ser configurado pelo responsável com a URL pública do servidor e o token correspondente.
