# Histórico aplicado do servidor do forno

Este registro distingue dados recuperados de hipóteses. Não contém segredos de rede.

## Configuração anterior registrada
- Raspberry Pi 3 com Flask, porta 5000, e serviço `forno.service` gerenciado pelo systemd.
- Configuração de serviço anterior: usuário `kelvin`, `app.py`, `Restart=always` e intervalo de 5 segundos.
- Foram documentados dois adaptadores de rede: `wlan0` para a rede local do ESP, `wlan1` para o acesso externo; uma rota estática era configurada por `setup_rede.sh`.
- ngrok foi instalado/configurado anteriormente; o token e o certificado da eduroam **não** fazem parte deste repositório.
- Os históricos citam caminhos diferentes (`~/forno` e `~/Downloads/forno`). O caminho real será verificado, não presumido.
- A referência a Raspbian 9.4 é antiga; **não** comprova a versão atual ou se o OS é 64-bit.

## Medidas preventivas
1. Não tocar na configuração de eduroam, hotspot, rota, WLAN ou serviços do forno.
2. Porta 5001 e serviço `labgateway-web.service` independentes.
3. Diretório `/opt/labgateway` e dados em `/var/lib/labgateway`.
4. Usuários Unix separados para web e worker; somente worker acessa Docker.
5. Diagnóstico somente leitura antes de instalar. Bloqueio explícito se o sistema não tiver suporte.
6. Criação de contas e instalações sempre com etapas visíveis, logs e confirmação.
7. Execução de código com timeout, recursos limitados e captura de saída limitada.
8. Sem alteração automática do túnel externo existente, pois sua porta, URL e configuração não foram confirmadas.
9. Backup da mídia antes de qualquer atualização de OS. Preferência por outro microSD para manter o forno intacto.
10. Validação de reinício, falhas de rede e acesso remoto antes de liberar contas de alunos.

## Limites conhecidos
Sem acesso físico não há como afirmar que SSH, Docker, sistema operacional, eduroam e ngrok estão funcionais atualmente. Contêineres Docker reduzem risco, mas não são garantia absoluta de isolamento de código hostil.
