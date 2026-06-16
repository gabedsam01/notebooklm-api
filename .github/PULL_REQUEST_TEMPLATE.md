## Resumo

<!-- O que muda e por quê. Issue relacionada: Fixes # -->

## Tipo de mudança

- [ ] Bugfix
- [ ] Feature
- [ ] Documentação
- [ ] Refactor / chore

## Checklist

- [ ] `pytest -q` passou
- [ ] `python -m compileall app tests` ok
- [ ] **Sem segredos** (token, cookie, `storage_state`, `Authorization`/`Bearer`)
- [ ] Não alterei o contrato público sem **documentar** (CHANGELOG/README/upgrade)
- [ ] **Não usei sessão real do Google** nos testes unitários (mocks/fakes)
- [ ] Atualizei a documentação se necessário
- [ ] Considerei impactos de **auth/CORS/scoping** e **erros seguros** (sem vazar paths/exceções cruas)
