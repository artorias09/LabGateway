# Plano de evolução — LabGateway

## v0.1 — Base de desenvolvimento (não homologada)
- [x] Flask, login, upload, papéis e painel
- [x] SQLite e fila administrada pelo professor
- [x] Worker Docker isolado e testes unitários básicos
- [ ] Integração real no Windows com Docker

## v0.2 — Segurança e robustez (branch feature/v02-deployment-readiness)
- [x] Implementação inicial de remoção de contêineres em timeout (teste real pendente)
- [ ] Rate limiting, auditoria, sessões e autenticação adicional
- [ ] Testes multiusuário, ZIPs malformados e isolamento
- [ ] Política de retenção, backup e restauração
- [ ] Contrato de submissão validado com professor

## v0.3 — Raspberry Pi 3
- [ ] Verificar arquitetura ARM64, RAM e sistema operacional
- [ ] Backup do projeto do forno
- [ ] Implantação com contas web/worker separadas
- [ ] 5 grupos, uma execução simultânea; recuperação após reinício

## v1.0 — Starlink + ngrok
- [ ] Conectividade e autenticação HTTPS
- [ ] Testes fim a fim e homologação de segurança

## Git
- `main`: base integrável
- `feature/*`: desenvolvimento
- `fix/*`: correções
- Tags só depois dos critérios de aceite
- Não versionar dados, credenciais ou uploads
