# Decisões registradas

- 2026-11-03: alvo de implantação: Raspberry Pi 3 do projeto do forno, sem formatação e preservando serviço existente.
- Rede institucional: eduroam USP, com autorização informada pelo usuário do professor e coordenação do campus.
- Acesso externo: ngrok já configurado para o forno, **não reutilizar o mesmo túnel/porta/URL sem avaliação**.
- LabGateway deve usar porta de desenvolvimento 5001, não 5000 (reservada ao forno).
- Upload de ZIP e execução apenas mediante solicitação do professor.
- Sem suporte garantido a GPIO, acesso à rede ou bibliotecas externas de alunos nesta fase.
- Não colocar certificados, credenciais, senhas ou tokens de túnel no repositório.
- Não prometer compatibilidade Docker na Raspberry antes de verificar arquitetura do OS e cgroups.
- Não expor código não confiável pela internet antes de completar testes de isolamento.
