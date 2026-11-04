# Implantação com reaproveitamento da infraestrutura do forno

## Decisão

Manter integralmente a instalação existente da Raspberry Pi 3, a eduroam, as duas interfaces de rede, as rotas, o servidor do forno e o agente ngrok. **Não formatar, reinstalar ou reconfigurar o que já opera.** O usuário confirmou que já fez backup da Raspberry.

O LabGateway será adicionado como aplicação independente, sem mudar a configuração de comunicação do forno.

| Componente do forno | Ação no LabGateway |
| --- | --- |
| Raspberry Pi OS e conexão eduroam | **Manter** se requisitos do executor forem compatíveis |
| `wlan0`, `wlan1`, redes de dispositivos e rotas | **Manter**, sem executar `setup_rede.sh` novamente |
| Flask do forno e serviço systemd | **Manter** na porta 5000 |
| ngrok existente | **Detectar e reutilizar o agente/instalação**, sem substituir token, serviço ou configuração |
| Serviços de aviso de URL (`notify-link`, `url-watcher`) | **Não modificar**. Confirmar nomes/estado reais |
| LabGateway | Novo app Gunicorn/Flask em `127.0.0.1:5001`, SQLite e worker separados |
| Execução de código dos alunos | **Exige Docker e validação de isolamento**; não rodar diretamente no Python do forno |

## O que foi confirmado no histórico

- Flask escutava na porta 5000 e recebia HTTP POST de sensores locais mesmo sem internet na interface do dispositivo.
- A Raspberry encaminhava os resultados à interface externa via outra conexão com internet e ngrok.
- Há referência de `forno.service` com usuário `kelvin` e caminho `/home/kelvin/Downloads/forno`.
- Também há histórico de `flask-app.service`, `ngrok.service`, `notify-link.service`, `url-watcher.service` e da API local do ngrok em `127.0.0.1:4040/api/tunnels`.
- Esses registros são históricos: **a existência atual, nomes definitivos, versão do sistema e tunel ativo precisam ser conferidos na Raspberry**.
- O histórico menciona rotas com mais de um adaptador Wi-Fi, mas não estabelece com segurança quais nomes/interface são usados hoje.

## Primeiro diagnóstico com HDMI, sem modificar nada

No terminal da Raspberry:

```bash
git clone -b feature/reuse-forno-infrastructure https://github.com/artorias09/LabGateway.git ~/LabGateway
cd ~/LabGateway
bash scripts/audit_forno_reuse.sh
bash scripts/preflight.sh
bash scripts/install_pi.sh --check
```

Se a pasta `~/LabGateway` já existir, não repetir clone: `cd ~/LabGateway && git fetch origin && git switch feature/reuse-forno-infrastructure`. O script de auditoria não imprime tokens nem certificados.

## Preservação

**Não executar:** `raspi-config`, alterações de NetworkManager/`wpa_supplicant`, `ip route add/del`, `setup_rede.sh`, `ngrok config add-authtoken`, mudanças no `ngrok.service`, reinício de `forno.service`, atualização total do SO ou scripts genéricos de instalação de Docker.

Separar tudo em `/opt/labgateway`, `/var/lib/labgateway` e `labgateway-web.service`/`labgateway-worker.service`. Criar contas locais independentes, nunca usar usuário `kelvin` para executar códigos dos alunos. Porta 5001, local, até validar isolamento.

## Acesso externo usando ngrok já instalado

O agente ngrok instalado anteriormente é reaproveitável, **mas a existência de um túnel para 5000 não implica túnel para 5001**. Primeiro identificar o serviço e sua forma de configuração **sem colar credenciais em relatórios**. Somente depois dos testes e com controle de acesso, adicionar endpoint separado ao agente existente caso o plano e a versão permitam múltiplos endpoints. Se não permitir, manter o forno intacto e avaliar plano ou encaminhamento autorizado, sem sobrescrever o túnel antigo. Não executar dois agentes usando a mesma configuração às cegas.

A API local `http://127.0.0.1:4040/api/tunnels` pode auxiliar na inspeção. Não publicar URL do forno nem token.

## Critérios de parada

- `uname -m` diferente de `aarch64`, Python abaixo de 3.10, Docker ausente/não funcional: interromper a instalação do executor e registrar diagnóstico. O forno continua funcionando.
- Não instalar uma stack de Docker incompatível no Raspberry Pi OS antigo.
- Falha em testes reais do container ou incerteza na segurança: não abrir ngrok para o LabGateway.
- Se houver problema no serviço novo: `sudo systemctl disable --now labgateway-web.service labgateway-worker.service`, sem tocar no forno.

## Limite funcional

A versão atual avalia programas Python com `main.py`, sem GPIO, sensores ou rede dentro dos containers. Protocolos da disciplina que exijam rede ainda precisam de cenário de teste isolado. Essa limitação não é solucionada pela configuração de rede que foi reutilizada do forno.
