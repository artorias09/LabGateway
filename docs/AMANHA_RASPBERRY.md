# Checklist de implantação — Raspberry Pi 3 / eduroam USP

**Objetivo de amanhã:** levantar a máquina e validar o LabGateway localmente. **Não liberar uploads reais nem executar código de alunos antes de homologar o isolamento.**

## 0. Acesso sem HDMI
Na mesma rede: `ssh kelvin@raspberrypi.local` (hostname é hipótese). Se o Raspberry não estiver na rede atual, usar Ethernet no roteador com DHCP; se necessário, descobrir o IP pelo painel do roteador. A eduroam pode bloquear comunicação lateral. Não inventar IP. Se o SSH não estiver habilitado, será necessário outro método de administração.

## 1. Preflight somente leitura
Após obter SSH:
```bash
git clone https://github.com/artorias09/LabGateway.git ~/LabGateway
cd ~/LabGateway
bash scripts/preflight.sh
```
**Atenção:** o comando acima acessa `main`; se as correções da v0.2 ainda estiverem em branch, fazer `git switch feature/v02-deployment-readiness` antes do preflight.

Verificar sistema (`uname -m`), RAM, espaço livre, Python, versão do Docker, Docker cgroups, eduroam, portas 5000/5001, forno.service e ngrok. **Não mostrar segredos, perfis Wi-Fi ou ngrok.yml em logs/screenshots.**

## 2. Regras de não interferência
- Não formatar cartão SD; não remover nem sobrescrever `/home/kelvin/Downloads/forno`.
- Não alterar `forno.service`, ngrok atual ou porta 5000.
- Não instalar Docker às cegas em Raspbian antigo. Verificar suporte à versão e arquitetura primeiro.
- Usar porta **5001** para o LabGateway; somente localhost até a validação.
- Garantir backup do forno antes de habilitar qualquer serviço novo.

## 3. Testes do código sem executor
```bash
cd ~/LabGateway
python3 -m unittest discover -s tests -v
python3 -m compileall -q app.py admin.py core.py store.py worker.py tests
```
Se faltar Flask, criar venv local e instalar `requirements.txt`, somente se a versão Python permitir. Verificar as dependências antes de atualizar o OS.

## 4. Validação Docker (condicional)
Somente após verificar SO/arquitetura, Docker e compatibilidade de cgroups:
```bash
docker pull python:3.12-alpine
docker run --rm --network none python:3.12-alpine python -c 'print("ok")'
```
O serviço web não pode ter acesso ao socket do Docker. A conta do worker com acesso ao Docker é altamente privilegiada; contêineres não são uma fronteira de segurança forte.

## 5. Rede institucional
A autorização do professor e coordenação foi informada. Reutilizar a configuração legítima de eduroam, sem copiar certificados/senhas para o repo. Para acesso externo, ngrok somente após testes de autenticação, revisão de segurança e aprovação do uso previsto. O túnel atual do forno não deve ser modificado.

## 6. Gate antes de alunos reais
- [ ] Testes de upload, login, permissões e CSRF
- [ ] Teste de timeout sem contêiner órfão e sem dano ao host
- [ ] Teste de travamento/reinício e recuperação da fila
- [ ] Testes de isolamento entre grupos, restrição de recursos e auditoria
- [ ] Teste de execução fim a fim na Raspberry
- [ ] Backup e rollback do forno confirmados
- [ ] Aprovação da versão final pelo professor
