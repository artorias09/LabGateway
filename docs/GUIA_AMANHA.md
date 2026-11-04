# LabGateway: roteiro da bancada para Raspberry Pi 3

**Não conectar o sistema aos alunos na primeira inicialização.** Primeiro confirmar rede, integridade do forno, ambiente Python/Docker e execução isolada.

## 1. Acesso sem HDMI

1. Ligar a Pi. Se estiver configurada apenas para a eduroam, ela pode não entrar no Wi-Fi doméstico.
2. Na USP, acessar via SSH pelo IP real, caso a rede permita. Alternativamente, conectar um cabo Ethernet a uma rede com DHCP.
3. Não presumir `raspberrypi.local`, IP ou o nome da interface de Wi-Fi. O roteamento do forno tinha duas interfaces.
4. Reutilizar os perfis eduroam e ngrok já existentes, sem os alterar. Não modificar `wlan0`, `wlan1`, `setup_rede.sh`, `forno.service` ou ngrok do forno.

## 2. Pré-diagnóstico

```bash
git clone -b fix/pi3-preflight-hardening https://github.com/artorias09/LabGateway.git ~/LabGateway
cd ~/LabGateway
bash scripts/audit_forno_reuse.sh\nbash scripts/preflight.sh
bash scripts/install_pi.sh --check
```

Se o usuário já tiver clonado o repositório, executar `git fetch` e `git switch fix/pi3-preflight-hardening` em vez de clonar novamente.

**Pare se:** `uname -m` não for `aarch64`, o Python for anterior ao 3.10, o Docker não estiver disponível, ou a Pi não tiver memória/espaço para operar. Não atualizar o OS do forno às cegas. Guarde o microSD original e prefira um segundo cartão para testes.

## 3. Preparar o ambiente somente após diagnóstico

Confirmar backup do forno, conectividade do repositório e disponibilidade dos pacotes. Examinar o instalador antes de executá-lo.

```bash
cd ~/LabGateway
sudo bash scripts/install_pi.sh --install
sudo bash scripts/create_pi_user.sh professor teacher
sudo bash scripts/create_pi_user.sh grupo01 student
sudo docker pull python:3.12-alpine
sudo bash scripts/smoke_pi.sh
```

**Se qualquer comando falhar:** não iniciar os serviços. Guardar a saída, corrigir a causa e só então retomar. O instalador bloqueia sobrescrita de diretórios existentes; uma instalação parcial deve ser inspecionada, não removida automaticamente.

## 4. Inspecionar e testar sem exposição externa

```bash
sudo systemctl cat forno.service
sudo systemctl cat labgateway-web.service
sudo systemctl cat labgateway-worker.service
sudo systemctl enable --now labgateway-web.service
sudo systemctl enable --now labgateway-worker.service
sudo systemctl status labgateway-web.service labgateway-worker.service --no-pager
curl -I http://127.0.0.1:5001/login
journalctl -u labgateway-web.service -n 40 --no-pager
journalctl -u labgateway-worker.service -n 40 --no-pager
```

Verificar no sistema que o forno continua usando a porta 5000. LabGateway usa 5001 apenas em localhost. A integração com ngrok ocorrerá **somente depois** da validação de autenticação, isolamento e política de rede. Não reutilizar o túnel existente.

## 5. Teste funcional completo

Na interface, entrar como aluno, enviar ZIP com `main.py`, sair, entrar como professor, abrir a submissão, executar e verificar resultado. Repetir com um programa que dá erro e outro que excede o limite de tempo. Conferir que o Docker não deixou contêineres e que o serviço do forno continua intacto.

## 6. Recuperação simples

Se o LabGateway apresentar problema:
```bash
sudo systemctl disable --now labgateway-web.service labgateway-worker.service
sudo systemctl status forno.service --no-pager
```

Não apagar banco, uploads, configuração de rede ou diretório do forno. Sem acesso ao SSH, usar Ethernet ou monitor antes de alterar o microSD.

## Pendências inadiáveis

- Verificação real do sistema instalado, compatibilidade ARM64, cgroups, Docker e permissões.
- Execução dos programas que seguem os protocolos da disciplina. A versão atual executa **Python com main.py**, sem internet ou GPIO dentro do contêiner.
- Segurança operacional para receber arquivos de terceiros, limitação de tentativas de login, retenção e auditoria.
- Separação do ngrok do forno e teste de acesso externo após homologação.

**Não declarar o servidor pronto para a turma antes de testar esses itens.**
