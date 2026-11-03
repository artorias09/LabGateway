# Instalação controlada na Raspberry Pi 3

Este projeto **não está liberado para uso por alunos reais**. Antes da exposição pública, homologar Docker real, execução adversarial, autenticação, limites, recuperação e integração de rede. O instalador faz verificações e não altera o projeto do forno.

## Equipamento
Usar Raspberry Pi 3, eduroam já autorizada pelo professor e coordenação. O monitoramento do forno usa a porta 5000 e deve permanecer intacto. LabGateway fica em 127.0.0.1:5001. O túnel ngrok do forno não será reaproveitado automaticamente.

## Primeiro acesso
Acessar por SSH. Sem Wi-Fi doméstico configurado, usar cabo Ethernet e DHCP com o roteador. Não presumir IP ou hostname. Não mostrar senhas, certificados ou token do ngrok.

```bash
git clone -b feature/v03-interface-release-prep https://github.com/artorias09/LabGateway.git ~/LabGateway
cd ~/LabGateway
bash scripts/preflight.sh
bash scripts/install_pi.sh --check
```

Se a arquitetura não for `aarch64`, **parar**. Não tentar forçar Docker atual no Raspbian 9 32-bit. Guardar o microSD existente e preparar outro microSD com Raspberry Pi OS 64-bit após backup e confirmação de suporte da variante da Pi 3.

## Instalação (apenas se todas as verificações passarem)

```bash
cd ~/LabGateway
sudo bash scripts/install_pi.sh --install
sudo bash scripts/create_pi_user.sh professor teacher
sudo bash scripts/create_pi_user.sh grupo01 student
```

Os serviços são copiados, mas **não são iniciados automaticamente**. Não há alterações no serviço do forno, na porta 5000, na eduroam ou no ngrok.

## Testes iniciais

```bash
cd ~/LabGateway
/opt/labgateway/.venv/bin/python -m unittest discover -s tests -v
docker pull python:3.12-alpine
sudo systemctl cat forno.service
sudo systemctl cat labgateway-web.service
sudo systemctl cat labgateway-worker.service
```

Antes da primeira execução real, verificar se a imagem foi carregada para Docker e testar limites de CPU, RAM, pids, timeout e limpeza de contêiner. Verificar acesso do `labrunner` ao grupo `docker` e acesso compartilhado a SQLite/uploads; se houver falhas, não iniciar os serviços.

## Habilitação controlada

Depois dos testes:
```bash
sudo systemctl enable --now labgateway-web.service
sudo systemctl enable --now labgateway-worker.service
sudo systemctl status labgateway-web.service labgateway-worker.service --no-pager
journalctl -u labgateway-web.service -n 60 --no-pager
journalctl -u labgateway-worker.service -n 60 --no-pager
curl -I http://127.0.0.1:5001/login
```

A interface ficará **somente na própria Raspberry** até que haja um encaminhamento autenticado. Não adicionar ngrok antes de revisar login e isolamento.

## Desfazer, sem tocar no forno
```bash
sudo systemctl disable --now labgateway-web.service labgateway-worker.service
```

Não excluir dados, contas ou diretórios automaticamente. Preservar uploads e o banco para diagnóstico. O serviço antigo do forno permanece separado.

## Problemas conhecidos do forno que o roteiro evita
- Caminhos absolutos e WorkingDirectory definidos para os serviços
- Serviço reiniciando sem checagem do log: usar `journalctl` e status
- Porta 5000 em uso: LabGateway na porta 5001
- Queda de túnel e URL pública alterada: o ngrok atual não é reutilizado e exige um serviço independente e monitoramento antes de liberar
- Rota dupla wlan0/wlan1: não alterar roteamento, interfaces ou eduroam por meio do instalador
- Reinício sem alimentação/serviços: verificar reboot e retorno do serviço em homologação
- Dispositivo com OS antigo: implantação interrompida antes de instalar incompatibilidades
